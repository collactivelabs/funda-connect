"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { hasUploadedAllRequiredDocuments } from "@/lib/teacher-documents";
import type { AvailabilitySlot, TeacherProfile, VerificationDocument } from "@/types";

interface Step {
  label: string;
  done: boolean;
  action?: () => void;
  actionLabel?: string;
}

interface Props {
  profile: TeacherProfile;
  availability: AvailabilitySlot[];
  documents: VerificationDocument[];
  onEditProfile: () => void;
  onManageSubjects: () => void;
  onSetAvailability: () => void;
}

export function OnboardingChecklist({
  profile,
  availability,
  documents,
  onEditProfile,
  onManageSubjects,
  onSetAvailability,
}: Props) {
  const documentsComplete = hasUploadedAllRequiredDocuments(documents);

  const steps: Step[] = [
    {
      label: "Set your hourly rate",
      done: !!profile.hourlyRateCents,
      action: onEditProfile,
      actionLabel: "Edit profile",
    },
    {
      label: "Add a bio and headline",
      done: !!profile.bio && !!profile.headline,
      action: onEditProfile,
      actionLabel: "Edit profile",
    },
    {
      label: "Add at least one subject",
      done: profile.subjects.length > 0,
      action: onManageSubjects,
      actionLabel: "Add subjects",
    },
    {
      label: "Set your availability",
      done: availability.length > 0,
      action: onSetAvailability,
      actionLabel: "Set hours",
    },
    {
      label: "Upload verification documents",
      done: documentsComplete,
    },
    {
      label: "Get verified by admin",
      done: profile.verificationStatus === "verified",
    },
  ];

  const completed = steps.filter((s) => s.done).length;

  // Hide once everything is done
  if (completed === steps.length) return null;

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">
          Get started — {completed}/{steps.length} complete
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {steps.map((step) => (
            <div
              key={step.label}
              className="flex items-center justify-between gap-4 text-sm"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className={step.done ? "text-primary" : "text-muted-foreground"}>
                  {step.done ? "\u2713" : "\u25CB"}
                </span>
                <span className={step.done ? "line-through text-muted-foreground" : ""}>
                  {step.label}
                </span>
              </div>
              {!step.done && step.action && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs shrink-0"
                  onClick={step.action}
                >
                  {step.actionLabel}
                </Button>
              )}
            </div>
          ))}
        </div>
        <div className="mt-3 h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${(completed / steps.length) * 100}%` }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
