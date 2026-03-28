"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import type { CurriculumOption, GradeLevelGroup, GradeLevelOption } from "@/types";

const FALLBACK_CURRICULA: CurriculumOption[] = [
  { code: "CAPS", label: "CAPS", description: "South African Curriculum and Assessment Policy Statement." },
  { code: "Cambridge", label: "Cambridge", description: "Cambridge homeschool and international programme support." },
  { code: "IEB", label: "IEB", description: "Independent Examinations Board aligned tutoring support." },
];

const FALLBACK_GRADE_LEVEL_GROUPS: GradeLevelGroup[] = [
  {
    phase: "Foundation Phase",
    items: [
      { value: "Grade R", label: "Grade R", order: 0 },
      { value: "Grade 1", label: "Grade 1", order: 1 },
      { value: "Grade 2", label: "Grade 2", order: 2 },
      { value: "Grade 3", label: "Grade 3", order: 3 },
    ],
  },
  {
    phase: "Intermediate Phase",
    items: [
      { value: "Grade 4", label: "Grade 4", order: 4 },
      { value: "Grade 5", label: "Grade 5", order: 5 },
      { value: "Grade 6", label: "Grade 6", order: 6 },
    ],
  },
  {
    phase: "Senior Phase",
    items: [
      { value: "Grade 7", label: "Grade 7", order: 7 },
      { value: "Grade 8", label: "Grade 8", order: 8 },
      { value: "Grade 9", label: "Grade 9", order: 9 },
    ],
  },
  {
    phase: "FET Phase",
    items: [
      { value: "Grade 10", label: "Grade 10", order: 10 },
      { value: "Grade 11", label: "Grade 11", order: 11 },
      { value: "Grade 12", label: "Grade 12", order: 12 },
    ],
  },
];

type ReferenceDataPayload = {
  curricula: CurriculumOption[];
  gradeLevelGroups: GradeLevelGroup[];
};

let referenceDataCache: ReferenceDataPayload | null = null;
let referenceDataPromise: Promise<ReferenceDataPayload> | null = null;
let referenceDataLastError: string | null = null;

export function flattenGradeLevelGroups(groups: GradeLevelGroup[]): GradeLevelOption[] {
  return groups.flatMap((group) => group.items).sort((left, right) => left.order - right.order);
}

async function loadReferenceData(): Promise<ReferenceDataPayload> {
  if (referenceDataCache) {
    return referenceDataCache;
  }

  if (!referenceDataPromise) {
    referenceDataPromise = Promise.all([
      apiClient.referenceData.listCurricula(),
      apiClient.referenceData.listGradeLevels(),
    ])
      .then(([curriculaResponse, gradeLevelsResponse]) => {
        referenceDataLastError = null;
        referenceDataCache = {
          curricula: curriculaResponse.data as CurriculumOption[],
          gradeLevelGroups: gradeLevelsResponse.data as GradeLevelGroup[],
        };
        return referenceDataCache;
      })
      .catch(() => {
        referenceDataLastError = "Could not load the latest reference data. Using local defaults.";
        referenceDataCache = {
          curricula: FALLBACK_CURRICULA,
          gradeLevelGroups: FALLBACK_GRADE_LEVEL_GROUPS,
        };
        return referenceDataCache;
      })
      .finally(() => {
        referenceDataPromise = null;
      });
  }

  return referenceDataPromise;
}

export function useReferenceData() {
  const [curricula, setCurricula] = useState<CurriculumOption[]>(referenceDataCache?.curricula ?? FALLBACK_CURRICULA);
  const [gradeLevelGroups, setGradeLevelGroups] = useState<GradeLevelGroup[]>(
    referenceDataCache?.gradeLevelGroups ?? FALLBACK_GRADE_LEVEL_GROUPS
  );
  const [loading, setLoading] = useState(referenceDataCache === null);
  const [error, setError] = useState<string | null>(referenceDataLastError);

  useEffect(() => {
    let cancelled = false;

    void loadReferenceData()
      .then((data) => {
        if (cancelled) {
          return;
        }
        setCurricula(data.curricula);
        setGradeLevelGroups(data.gradeLevelGroups);
        setError(referenceDataLastError);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    curricula,
    gradeLevelGroups,
    gradeLevels: flattenGradeLevelGroups(gradeLevelGroups),
    loading,
    error,
  };
}
