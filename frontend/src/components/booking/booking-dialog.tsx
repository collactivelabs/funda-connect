"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";
import type { ApiError, BookableSlot, Learner, TeacherProfile, TeacherSubject } from "@/types";
import type { AxiosError } from "axios";

const DURATION_OPTIONS = [
  { value: 30, label: "30 minutes" },
  { value: 60, label: "1 hour" },
  { value: 90, label: "1.5 hours" },
  { value: 120, label: "2 hours" },
  { value: 150, label: "2.5 hours" },
  { value: 180, label: "3 hours" },
];

interface BookingDialogProps {
  teacher: TeacherProfile;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface PayFastRedirectPayload {
  paymentUrl: string;
  formData?: Record<string, string>;
}

function learnerCanBookSubject(learner: Learner, subject: TeacherSubject) {
  return (
    subject.curriculum === learner.curriculum
    && (subject.gradeLevels.length === 0 || subject.gradeLevels.includes(learner.grade))
  );
}

function toSnakeCaseKey(key: string) {
  return key.replace(/([A-Z])/g, "_$1").toLowerCase();
}

function submitPayFastForm(action: string, fields: Record<string, string>) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = action;
  form.style.display = "none";

  for (const [key, value] of Object.entries(fields)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = toSnakeCaseKey(key);
    input.value = value;
    form.appendChild(input);
  }

  document.body.appendChild(form);
  form.submit();
}

export function BookingDialog({ teacher, open, onOpenChange }: BookingDialogProps) {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [learners, setLearners] = useState<Learner[]>([]);
  const [loadingLearners, setLoadingLearners] = useState(false);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slotError, setSlotError] = useState<string | null>(null);

  const [learnerId, setLearnerId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedSlotStart, setSelectedSlotStart] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [isTrial, setIsTrial] = useState(false);
  const [isRecurring, setIsRecurring] = useState(false);
  const [recurringWeeks, setRecurringWeeks] = useState(4);
  const [bookableSlots, setBookableSlots] = useState<BookableSlot[]>([]);

  const selectedLearner = learners.find((learner) => learner.id === learnerId) ?? null;
  const availableSubjects = selectedLearner
    ? teacher.subjects.filter((subject) => learnerCanBookSubject(selectedLearner, subject))
    : [];

  const dateOptions: Array<{ value: string; label: string }> = [];
  const seenDates = new Set<string>();
  for (const slot of bookableSlots) {
    if (!seenDates.has(slot.date)) {
      seenDates.add(slot.date);
      dateOptions.push({ value: slot.date, label: slot.dateLabel });
    }
  }

  const timeOptions = selectedDate
    ? bookableSlots.filter((slot) => slot.date === selectedDate)
    : [];

  const amountCents = teacher.hourlyRateCents
    ? Math.floor(teacher.hourlyRateCents * durationMinutes / 60)
    : null;
  const totalChargeCents = amountCents !== null
    ? amountCents * (isRecurring ? recurringWeeks : 1)
    : null;

  useEffect(() => {
    if (!open) return;
    setError(null);
    setSlotError(null);
  }, [open]);

  useEffect(() => {
    if (open && !user) {
      onOpenChange(false);
      router.push(`/login?redirect=/teachers/${teacher.id}`);
    }
  }, [open, onOpenChange, router, teacher.id, user]);

  useEffect(() => {
    if (open && user?.role === "teacher") {
      onOpenChange(false);
    }
  }, [open, onOpenChange, user]);

  useEffect(() => {
    if (!open || !user || user.role !== "parent") return;

    let cancelled = false;
    setLoadingLearners(true);

    apiClient.parents.getLearners()
      .then(({ data }) => {
        if (cancelled) return;
        setLearners(data as Learner[]);
      })
      .catch(() => {
        if (cancelled) return;
        setLearners([]);
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingLearners(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open, user]);

  useEffect(() => {
    if (learnerId && !learners.some((learner) => learner.id === learnerId)) {
      setLearnerId("");
    }
  }, [learnerId, learners]);

  useEffect(() => {
    if (!selectedLearner) {
      setSubjectId("");
      return;
    }

    const nextSubjects = teacher.subjects.filter((subject) => learnerCanBookSubject(selectedLearner, subject));
    if (!nextSubjects.some((subject) => subject.subjectId === subjectId)) {
      setSubjectId("");
    }
  }, [selectedLearner, subjectId, teacher.subjects]);

  useEffect(() => {
    if (!selectedDate) {
      setSelectedSlotStart("");
      return;
    }

    const nextTimeOptions = bookableSlots.filter((slot) => slot.date === selectedDate);
    if (!nextTimeOptions.some((slot) => slot.startAt === selectedSlotStart)) {
      setSelectedSlotStart("");
    }
  }, [bookableSlots, selectedDate, selectedSlotStart]);

  useEffect(() => {
    if (!open || !user || user.role !== "parent") return;

    let cancelled = false;
    setLoadingSlots(true);
    setSlotError(null);

    apiClient.teachers.getBookableSlots(teacher.id, {
      durationMinutes,
      recurringWeeks: isRecurring ? recurringWeeks : 1,
    })
      .then(({ data }) => {
        if (cancelled) return;

        const nextSlots = data as BookableSlot[];
        setBookableSlots(nextSlots);
        setSelectedDate((currentDate) => (
          nextSlots.some((slot) => slot.date === currentDate)
            ? currentDate
            : (nextSlots[0]?.date ?? "")
        ));
        setSelectedSlotStart("");
      })
      .catch((err) => {
        if (cancelled) return;

        const axiosErr = err as AxiosError<ApiError>;
        setBookableSlots([]);
        setSelectedDate("");
        setSelectedSlotStart("");
        setSlotError(
          axiosErr.response?.data?.detail
            ?? "We couldn't load the teacher's available slots. Please try again."
        );
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingSlots(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [durationMinutes, isRecurring, open, recurringWeeks, teacher.id, user]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!learnerId || !subjectId || !selectedSlotStart) {
      setError("Please complete all required fields.");
      return;
    }

    setSubmitting(true);

    try {
      const { data } = await apiClient.bookings.create({
        teacher_id: teacher.id,
        learner_id: learnerId,
        subject_id: subjectId,
        scheduled_at: selectedSlotStart,
        duration_minutes: durationMinutes,
        is_trial: isTrial,
        is_recurring: isRecurring,
        recurring_weeks: isRecurring ? recurringWeeks : undefined,
      });

      const { paymentUrl, formData } = data as PayFastRedirectPayload;
      if (formData && Object.keys(formData).length > 0) {
        submitPayFastForm(paymentUrl, formData);
        return;
      }

      window.location.href = paymentUrl;
    } catch (err) {
      const axiosErr = err as AxiosError<ApiError>;
      setError(axiosErr.response?.data?.detail ?? "Failed to create booking. Please try again.");
      setSubmitting(false);
    }
  }

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
          <div className="space-y-1.5">
            <Label htmlFor="learner">Learner *</Label>
            {loadingLearners ? (
              <p className="text-sm text-muted-foreground">Loading learners…</p>
            ) : learners.length === 0 ? (
              <Alert>
                <AlertDescription>
                  You have no learners yet.{" "}
                  <button
                    type="button"
                    className="underline"
                    onClick={() => {
                      onOpenChange(false);
                      router.push("/parent");
                    }}
                  >
                    Add a learner
                  </button>{" "}
                  from your dashboard first.
                </AlertDescription>
              </Alert>
            ) : (
              <Select value={learnerId} onValueChange={(value) => setLearnerId(value ?? "")}>
                <SelectTrigger id="learner">
                  <SelectValue placeholder="Select learner" />
                </SelectTrigger>
                <SelectContent>
                  {learners.map((learner) => (
                    <SelectItem key={learner.id} value={learner.id}>
                      {learner.firstName} {learner.lastName} - {learner.grade}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="subject">Subject *</Label>
            <Select
              value={subjectId}
              onValueChange={(value) => setSubjectId(value ?? "")}
              disabled={!selectedLearner || availableSubjects.length === 0}
            >
              <SelectTrigger id="subject">
                <SelectValue placeholder={selectedLearner ? "Select subject" : "Select learner first"} />
              </SelectTrigger>
              <SelectContent>
                {availableSubjects.map((subject) => (
                  <SelectItem key={subject.id} value={subject.subjectId}>
                    {subject.subjectName} ({subject.curriculum})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedLearner && availableSubjects.length === 0 && (
              <Alert>
                <AlertDescription>
                  This teacher has no subject set up for {selectedLearner.grade} {selectedLearner.curriculum}.
                </AlertDescription>
              </Alert>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="duration">Duration</Label>
            <Select
              value={String(durationMinutes)}
              onValueChange={(value) => setDurationMinutes(Number(value))}
            >
              <SelectTrigger id="duration">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DURATION_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={String(option.value)}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="trial"
              type="checkbox"
              checked={isTrial}
              onChange={(event) => setIsTrial(event.target.checked)}
              className="h-4 w-4 rounded border"
            />
            <Label htmlFor="trial" className="cursor-pointer font-normal">
              This is a trial lesson
            </Label>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input
                id="recurring"
                type="checkbox"
                checked={isRecurring}
                onChange={(event) => setIsRecurring(event.target.checked)}
                className="h-4 w-4 rounded border"
              />
              <Label htmlFor="recurring" className="cursor-pointer font-normal">
                Recurring weekly
              </Label>
            </div>
            {isRecurring && (
              <div className="ml-6 flex items-center gap-2">
                <Label
                  htmlFor="recurring_weeks"
                  className="whitespace-nowrap text-sm font-normal text-muted-foreground"
                >
                  Number of weeks:
                </Label>
                <input
                  id="recurring_weeks"
                  type="number"
                  min={2}
                  max={12}
                  value={recurringWeeks}
                  onChange={(event) => {
                    const nextValue = Number(event.target.value);
                    setRecurringWeeks(Math.min(12, Math.max(2, nextValue || 2)));
                  }}
                  className="flex h-8 w-20 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
                <span className="text-sm text-muted-foreground">({recurringWeeks} lessons)</span>
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="booking-date">Date *</Label>
            {loadingSlots ? (
              <p className="text-sm text-muted-foreground">Loading available slots…</p>
            ) : slotError ? (
              <Alert variant="destructive">
                <AlertDescription>{slotError}</AlertDescription>
              </Alert>
            ) : bookableSlots.length === 0 ? (
              <Alert>
                <AlertDescription>
                  No slots are currently available for this lesson length
                  {isRecurring ? ` across ${recurringWeeks} weeks` : ""}. Try another duration or check back later.
                </AlertDescription>
              </Alert>
            ) : (
              <>
                <Select
                  value={selectedDate}
                  onValueChange={(value) => {
                    setSelectedDate(value ?? "");
                    setSelectedSlotStart("");
                  }}
                >
                  <SelectTrigger id="booking-date">
                    <SelectValue placeholder="Select date" />
                  </SelectTrigger>
                  <SelectContent>
                    {dateOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <div className="space-y-1.5 pt-2">
                  <Label htmlFor="booking-time">Time *</Label>
                  <Select
                    value={selectedSlotStart}
                    onValueChange={(value) => setSelectedSlotStart(value ?? "")}
                    disabled={!selectedDate}
                  >
                    <SelectTrigger id="booking-time">
                      <SelectValue placeholder="Select time" />
                    </SelectTrigger>
                    <SelectContent>
                      {timeOptions.map((slot) => (
                        <SelectItem key={slot.startAt} value={slot.startAt}>
                          {slot.timeLabel}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
            {isRecurring && bookableSlots.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Only weekly start times available for all {recurringWeeks} weeks are shown.
              </p>
            )}
          </div>

          {amountCents !== null && (
            <>
              <Separator />
              {isRecurring ? (
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Per lesson</span>
                    <span>R{(amountCents / 100).toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Weekly series</span>
                    <span className="font-semibold">{recurringWeeks} lessons</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Due today</span>
                    <span className="text-base font-semibold">
                      R{((totalChargeCents ?? 0) / 100).toFixed(2)}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Total</span>
                  <span className="text-base font-semibold">
                    R{(amountCents / 100).toFixed(2)}
                  </span>
                </div>
              )}
              <p className="text-xs text-muted-foreground -mt-2">
                {isRecurring
                  ? "You'll be redirected to PayFast to pay for the full weekly series upfront. Your slot will be held for 15 minutes while payment is pending."
                  : "You'll be redirected to PayFast to complete payment. Your slot will be held for 15 minutes while payment is pending."}
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
              disabled={
                submitting
                || learners.length === 0
                || !learnerId
                || !subjectId
                || !selectedSlotStart
                || loadingSlots
              }
            >
              {submitting ? "Creating…" : "Book & Pay"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
