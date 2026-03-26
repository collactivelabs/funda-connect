"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";
import type { ApiError, Learner, TeacherProfile, TeacherSubject } from "@/types";
import type { AxiosError } from "axios";

const DURATION_OPTIONS = [
  { value: 30, label: "30 minutes" },
  { value: 60, label: "1 hour" },
  { value: 90, label: "1.5 hours" },
  { value: 120, label: "2 hours" },
];

interface BookingDialogProps {
  teacher: TeacherProfile;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BookingDialog({ teacher, open, onOpenChange }: BookingDialogProps) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  const [learners, setLearners] = useState<Learner[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [learnerId, setLearnerId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [isTrial, setIsTrial] = useState(false);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (open && !user) {
      onOpenChange(false);
      router.push(`/login?redirect=/teachers/${teacher.id}`);
    }
  }, [open, user, router, teacher.id, onOpenChange]);

  // Redirect teachers away — only parents can book
  useEffect(() => {
    if (open && user?.role === "teacher") {
      onOpenChange(false);
    }
  }, [open, user, onOpenChange]);

  // Load parent's learners when dialog opens
  useEffect(() => {
    if (!open || !user || user.role !== "parent") return;
    setLoading(true);
    apiClient.parents.getLearners()
      .then(({ data }) => setLearners(data as Learner[]))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [open, user]);

  // Price preview
  const selectedSubject: TeacherSubject | undefined = teacher.subjects.find(
    (s) => s.subjectId === subjectId
  );
  const amountCents = teacher.hourlyRateCents
    ? Math.floor(teacher.hourlyRateCents * durationMinutes / 60)
    : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!learnerId || !subjectId || !scheduledAt) {
      setError("Please complete all required fields.");
      return;
    }

    setSubmitting(true);
    try {
      const { data } = await apiClient.bookings.create({
        teacher_id: teacher.id,
        learner_id: learnerId,
        subject_id: subjectId,
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_minutes: durationMinutes,
        is_trial: isTrial,
      });

      // Redirect to PayFast
      const { payment_url } = data as { payment_url: string };
      window.location.href = payment_url;
    } catch (err) {
      const axiosErr = err as AxiosError<ApiError>;
      setError(axiosErr.response?.data?.detail ?? "Failed to create booking. Please try again.");
      setSubmitting(false);
    }
  }

  // Minimum datetime: now + 1 hour, rounded to 15 min
  const minDatetime = (() => {
    const d = new Date(Date.now() + 60 * 60 * 1000);
    d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15, 0, 0);
    return d.toISOString().slice(0, 16);
  })();

  if (!user || user.role !== "parent") return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Book a Lesson</DialogTitle>
          <DialogDescription>
            with {teacher.user.firstName} {teacher.user.lastName}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {/* Learner */}
          <div className="space-y-1.5">
            <Label htmlFor="learner">Learner *</Label>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading learners…</p>
            ) : learners.length === 0 ? (
              <Alert>
                <AlertDescription>
                  You have no learners yet.{" "}
                  <button
                    type="button"
                    className="underline"
                    onClick={() => { onOpenChange(false); router.push("/parent"); }}
                  >
                    Add a learner
                  </button>{" "}
                  from your dashboard first.
                </AlertDescription>
              </Alert>
            ) : (
              <Select value={learnerId} onValueChange={(v) => setLearnerId(v ?? "")} required>
                <SelectTrigger id="learner">
                  <SelectValue placeholder="Select learner" />
                </SelectTrigger>
                <SelectContent>
                  {learners.map((l) => (
                    <SelectItem key={l.id} value={l.id}>
                      {l.firstName} {l.lastName} — {l.grade}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Subject */}
          <div className="space-y-1.5">
            <Label htmlFor="subject">Subject *</Label>
            <Select value={subjectId} onValueChange={(v) => setSubjectId(v ?? "")} required>
              <SelectTrigger id="subject">
                <SelectValue placeholder="Select subject" />
              </SelectTrigger>
              <SelectContent>
                {teacher.subjects.map((s) => (
                  <SelectItem key={s.subjectId} value={s.subjectId}>
                    {s.subjectName} ({s.curriculum})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Date & time */}
          <div className="space-y-1.5">
            <Label htmlFor="scheduled_at">Date & time *</Label>
            <input
              id="scheduled_at"
              type="datetime-local"
              min={minDatetime}
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              required
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          {/* Duration */}
          <div className="space-y-1.5">
            <Label htmlFor="duration">Duration</Label>
            <Select
              value={String(durationMinutes)}
              onValueChange={(v) => setDurationMinutes(Number(v))}
            >
              <SelectTrigger id="duration">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DURATION_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={String(o.value)}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Trial toggle */}
          <div className="flex items-center gap-2">
            <input
              id="trial"
              type="checkbox"
              checked={isTrial}
              onChange={(e) => setIsTrial(e.target.checked)}
              className="h-4 w-4 rounded border"
            />
            <Label htmlFor="trial" className="cursor-pointer font-normal">
              This is a trial lesson
            </Label>
          </div>

          {/* Price summary */}
          {amountCents !== null && (
            <>
              <Separator />
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Total</span>
                <span className="font-semibold text-base">
                  R{(amountCents / 100).toFixed(2)}
                </span>
              </div>
              <p className="text-xs text-muted-foreground -mt-2">
                You'll be redirected to PayFast to complete payment.
              </p>
            </>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="flex-1"
              disabled={submitting || learners.length === 0}
            >
              {submitting ? "Creating…" : "Book & Pay"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
