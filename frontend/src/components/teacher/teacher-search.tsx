"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { useReferenceData } from "@/lib/reference-data";
import type { Subject, TeacherProfile, TeacherSearchParams } from "@/types";
import { TeacherCard } from "./teacher-card";

const PROVINCES = [
  "Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal",
  "Limpopo", "Mpumalanga", "North West", "Northern Cape", "Western Cape",
];

const SORT_OPTIONS = [
  { value: "rating_average:desc", label: "Top rated" },
  { value: "hourly_rate_cents:asc", label: "Price: low to high" },
  { value: "hourly_rate_cents:desc", label: "Price: high to low" },
  { value: "total_lessons:desc", label: "Most lessons taught" },
  { value: "created_at:desc", label: "Newest profiles" },
] as const;

const RATING_OPTIONS = [
  { value: 4.5, label: "4.5 stars and up" },
  { value: 4, label: "4 stars and up" },
  { value: 3.5, label: "3.5 stars and up" },
] as const;

function parseFilters(searchParams: { get(name: string): string | null }): TeacherSearchParams {
  const minRate = searchParams.get("min_rate");
  const maxRate = searchParams.get("max_rate");
  const minRating = searchParams.get("min_rating");

  return {
    q: searchParams.get("q") || undefined,
    subject: searchParams.get("subject") || undefined,
    curriculum: (searchParams.get("curriculum") as TeacherSearchParams["curriculum"] | null) || undefined,
    grade: searchParams.get("grade") || undefined,
    province: searchParams.get("province") || undefined,
    minRate: minRate ? Number(minRate) : undefined,
    maxRate: maxRate ? Number(maxRate) : undefined,
    minRating: minRating ? Number(minRating) : undefined,
    sortBy: (searchParams.get("sort_by") as TeacherSearchParams["sortBy"] | null) || undefined,
    sortOrder: (searchParams.get("sort_order") as TeacherSearchParams["sortOrder"] | null) || undefined,
  };
}

function buildFilterParams(filters: TeacherSearchParams): URLSearchParams {
  const params = new URLSearchParams();

  if (filters.subject) params.set("subject", filters.subject);
  if (filters.q) params.set("q", filters.q);
  if (filters.curriculum) params.set("curriculum", filters.curriculum);
  if (filters.grade) params.set("grade", filters.grade);
  if (filters.province) params.set("province", filters.province);
  if (filters.minRate != null) params.set("min_rate", String(filters.minRate));
  if (filters.maxRate != null) params.set("max_rate", String(filters.maxRate));
  if (filters.minRating != null) params.set("min_rating", String(filters.minRating));
  if (filters.sortBy) params.set("sort_by", filters.sortBy);
  if (filters.sortOrder) params.set("sort_order", filters.sortOrder);

  return params;
}

function parseFiltersFromString(search: string): TeacherSearchParams {
  return parseFilters(new URLSearchParams(search));
}

function ResultsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-48" />
      ))}
    </div>
  );
}

export function TeacherSearch() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [teachers, setTeachers] = useState<TeacherProfile[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();
  const { curricula, gradeLevels } = useReferenceData();
  const searchParamKey = searchParams.toString();
  const filters = useMemo(() => parseFiltersFromString(searchParamKey), [searchParamKey]);

  useEffect(() => {
    apiClient.subjects.list()
      .then(({ data }) => setSubjects(data as Subject[]))
      .catch(() => null);
  }, []);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (filters.subject) params.subject = filters.subject;
    if (filters.q) params.q = filters.q;
    if (filters.curriculum) params.curriculum = filters.curriculum;
    if (filters.grade) params.grade = filters.grade;
    if (filters.province) params.province = filters.province;
    if (filters.minRate != null) params.min_rate = String(filters.minRate * 100);
    if (filters.maxRate != null) params.max_rate = String(filters.maxRate * 100);
    if (filters.minRating != null) params.min_rating = String(filters.minRating);
    if (filters.sortBy) params.sort_by = filters.sortBy;
    if (filters.sortOrder) params.sort_order = filters.sortOrder;

    apiClient.teachers.search(params)
      .then(({ data }) => setTeachers(data as TeacherProfile[]))
      .catch(() => setTeachers([]))
      .finally(() => setLoading(false));
  }, [filters]);

  function replaceFilters(nextFilters: TeacherSearchParams) {
    setLoading(true);
    startTransition(() => {
      const next = buildFilterParams(nextFilters).toString();
      router.replace(next ? `${pathname}?${next}` : pathname, { scroll: false });
    });
  }

  function setFilter<K extends keyof TeacherSearchParams>(key: K, value: TeacherSearchParams[K]) {
    replaceFilters({ ...filters, [key]: value });
  }

  function clearFilter<K extends keyof TeacherSearchParams>(key: K) {
    const next = { ...filters };
    delete next[key];
    replaceFilters(next);
  }

  const activeFilters = Object.entries(filters).filter(
    ([key, value]) => value !== undefined && key !== "sortBy" && key !== "sortOrder"
  );

  function getFilterLabel(key: string, value: string | number) {
    switch (key) {
      case "q":
        return `Search: ${value}`;
      case "subject":
        return `Subject: ${subjects.find((subject) => subject.slug === value)?.name ?? value}`;
      case "curriculum":
        return `Curriculum: ${curricula.find((item) => item.code === value)?.label ?? value}`;
      case "grade":
        return `Grade: ${value}`;
      case "province":
        return `Province: ${value}`;
      case "minRate":
        return `Min rate: R${value}`;
      case "maxRate":
        return `Max rate: R${value}`;
      case "minRating":
        return `Rating: ${value}+`;
      default:
        return String(value);
    }
  }

  return (
    <div className="flex flex-col gap-8 lg:flex-row">
      {/* Filters sidebar */}
      <aside className="w-full lg:w-64 shrink-0 space-y-6">
        <div>
          <h2 className="font-semibold mb-4">Filters</h2>
          <div className="space-y-4">
            {/* Subject */}
            <div className="space-y-1.5">
              <Label>Subject</Label>
              <Select
                value={filters.subject ?? ""}
                onValueChange={(v) => v ? setFilter("subject", v) : clearFilter("subject")}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any subject" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Any subject</SelectItem>
                  {subjects.map((s) => (
                    <SelectItem key={s.id} value={s.slug}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Curriculum */}
            <div className="space-y-1.5">
              <Label>Curriculum</Label>
              <Select
                value={filters.curriculum ?? ""}
                onValueChange={(v) => v ? setFilter("curriculum", v as TeacherSearchParams["curriculum"]) : clearFilter("curriculum")}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any curriculum" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Any curriculum</SelectItem>
                  {curricula.map((curriculum) => (
                    <SelectItem key={curriculum.code} value={curriculum.code}>{curriculum.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Grade */}
            <div className="space-y-1.5">
              <Label>Grade</Label>
              <Select
                value={filters.grade ?? ""}
                onValueChange={(v) => v ? setFilter("grade", v) : clearFilter("grade")}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any grade" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Any grade</SelectItem>
                  {gradeLevels.map((grade) => (
                    <SelectItem key={grade.value} value={grade.value}>{grade.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Province */}
            <div className="space-y-1.5">
              <Label>Province</Label>
              <Select
                value={filters.province ?? ""}
                onValueChange={(v) => v ? setFilter("province", v) : clearFilter("province")}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any province" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Any province</SelectItem>
                  {PROVINCES.map((p) => (
                    <SelectItem key={p} value={p}>{p}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Rate range */}
            <div className="space-y-1.5">
              <Label>Hourly rate (R)</Label>
              <div className="flex gap-2">
                <Input
                  type="number"
                  placeholder="Min"
                  min={0}
                  className="w-full"
                  value={filters.minRate ?? ""}
                  onChange={(e) => {
                    const v = e.target.value ? Number(e.target.value) : undefined;
                    if (v !== undefined) {
                      setFilter("minRate", v);
                    } else {
                      clearFilter("minRate");
                    }
                  }}
                />
                <Input
                  type="number"
                  placeholder="Max"
                  min={0}
                  className="w-full"
                  value={filters.maxRate ?? ""}
                  onChange={(e) => {
                    const v = e.target.value ? Number(e.target.value) : undefined;
                    if (v !== undefined) {
                      setFilter("maxRate", v);
                    } else {
                      clearFilter("maxRate");
                    }
                  }}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Minimum rating</Label>
              <Select
                value={filters.minRating != null ? String(filters.minRating) : ""}
                onValueChange={(value) => value ? setFilter("minRating", Number(value)) : clearFilter("minRating")}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any rating" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Any rating</SelectItem>
                  {RATING_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={String(option.value)}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {activeFilters.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                onClick={() => replaceFilters({})}
              >
                Clear all filters
              </Button>
            )}
          </div>
        </div>
      </aside>

      <Separator orientation="vertical" className="hidden lg:block" />

      {/* Results */}
      <div className="flex-1 min-w-0">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1.5 sm:max-w-sm">
            <Label htmlFor="teacherSearchQuery">Search teachers</Label>
            <Input
              id="teacherSearchQuery"
              placeholder="Search by teacher name, bio, or subject"
              value={filters.q ?? ""}
              onChange={(e) => {
                const value = e.target.value.trimStart();
                if (value) {
                  setFilter("q", value);
                } else {
                  clearFilter("q");
                }
              }}
            />
          </div>

          <div className="space-y-1.5 sm:w-56">
            <Label>Sort by</Label>
            <Select
              value={filters.sortBy ? `${filters.sortBy}:${filters.sortOrder ?? "desc"}` : ""}
              onValueChange={(value) => {
                if (!value) {
                  clearFilter("sortBy");
                  clearFilter("sortOrder");
                  return;
                }
                const [sortBy, sortOrder] = value.split(":") as [TeacherSearchParams["sortBy"], TeacherSearchParams["sortOrder"]];
                setFilter("sortBy", sortBy);
                setFilter("sortOrder", sortOrder);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Recommended" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Recommended</SelectItem>
                {SORT_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Active filter chips */}
        {activeFilters.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {activeFilters.map(([key, value]) => (
              <Badge
                key={key}
                variant="secondary"
                className="cursor-pointer"
                onClick={() => clearFilter(key as keyof TeacherSearchParams)}
              >
                {getFilterLabel(key, value as string | number)} ×
              </Badge>
            ))}
          </div>
        )}

        {loading || isPending ? (
          <ResultsSkeleton />
        ) : teachers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="text-muted-foreground">No teachers found matching your filters.</p>
            {activeFilters.length > 0 && (
              <Button
                variant="link"
                onClick={() => replaceFilters({})}
              >
                Clear filters
              </Button>
            )}
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground mb-4">
              {teachers.length} teacher{teachers.length !== 1 ? "s" : ""} found
            </p>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {teachers.map((t) => (
                <TeacherCard key={t.id} teacher={t} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
