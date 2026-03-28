"use client";

import { useMemo, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiClient } from "@/lib/api";
import type { ApiError, BookableSlot, Booking } from "@/types";
import type { AxiosError } from "axios";

function getErrorMessage(error: unknown, fallback: string) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;
}

function sameMoment(left: string, right: string) {
  return new Date(left).getTime() === new Date(right).getTime();
}

export function RescheduleBookingDialog({
  booking,
  onRescheduled,
}: {
  booking: Booking;
  onRescheduled: (patch: Partial<Booking>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slotError, setSlotError] = useState<string | null>(null);
  const [bookableSlots, setBookableSlots] = useState<BookableSlot[]>([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedSlotStart, setSelectedSlotStart] = useState("");

  const filteredSlots = useMemo(
    () => bookableSlots.filter((slot) => !sameMoment(slot.startAt, booking.scheduledAt)),
    [bookableSlots, booking.scheduledAt],
  );

  const dateOptions = useMemo(() => {
    const nextOptions: Array<{ value: string; label: string }> = [];
    const seen = new Set<string>();

    for (const slot of filteredSlots) {
      if (!seen.has(slot.date)) {
        seen.add(slot.date);
        nextOptions.push({ value: slot.date, label: slot.dateLabel });
      }
    }

    return nextOptions;
  }, [filteredSlots]);

  const timeOptions = useMemo(
    () => (selectedDate ? filteredSlots.filter((slot) => slot.date === selectedDate) : []),
    [filteredSlots, selectedDate],
  );

  async function loadSlots() {
    setLoadingSlots(true);
    setSlotError(null);

    try {
      const { data } = await apiClient.teachers.getBookableSlots(booking.teacherId, {
        durationMinutes: booking.durationMinutes,
        ignoreBookingId: booking.id,
      });
      const nextSlots = data as BookableSlot[];
      const availableSlots = nextSlots.filter((slot) => !sameMoment(slot.startAt, booking.scheduledAt));
      setBookableSlots(availableSlots);
      setSelectedDate(availableSlots[0]?.date ?? "");
      setSelectedSlotStart("");
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<ApiError>;
      setBookableSlots([]);
      setSelectedDate("");
      setSelectedSlotStart("");
      setSlotError(
        axiosErr.response?.data?.detail
          ?? "We couldn't load alternate slots right now. Please try again."
      );
    } finally {
      setLoadingSlots(false);
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen);
    setError(null);
    if (nextOpen) {
      void loadSlots();
      return;
    }
    setSlotError(null);
    setBookableSlots([]);
    setSelectedDate("");
    setSelectedSlotStart("");
  }

  async function handleSubmit() {
    if (!selectedSlotStart) {
      setError("Please choose a new date and time.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const { data } = await apiClient.bookings.reschedule(booking.id, {
        scheduled_at: selectedSlotStart,
      });
      const nextBooking = data as Booking;
      onRescheduled({
        scheduledAt: nextBooking.scheduledAt,
        status: nextBooking.status,
        videoRoomUrl: nextBooking.videoRoomUrl,
      });
      handleOpenChange(false);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not reschedule this lesson."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="text-xs h-7"
        onClick={() => handleOpenChange(true)}
      >
        Reschedule
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Reschedule lesson</DialogTitle>
            <DialogDescription>
              Choose a new time that still works for the teacher.
              {booking.isRecurring ? " This only moves this one lesson." : ""}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
              Current lesson: {new Date(booking.scheduledAt).toLocaleString("en-ZA", {
                weekday: "short",
                day: "numeric",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>

            {slotError ? (
              <Alert variant="destructive">
                <AlertDescription>{slotError}</AlertDescription>
              </Alert>
            ) : loadingSlots ? (
              <p className="text-sm text-muted-foreground">Loading available slots...</p>
            ) : filteredSlots.length === 0 ? (
              <Alert>
                <AlertDescription>
                  No alternate slots are currently available for this lesson length.
                </AlertDescription>
              </Alert>
            ) : (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="reschedule-date">Date</Label>
                  <Select
                    value={selectedDate}
                    onValueChange={(value) => {
                      setSelectedDate(value ?? "");
                      setSelectedSlotStart("");
                    }}
                  >
                    <SelectTrigger id="reschedule-date">
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
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="reschedule-time">Time</Label>
                  <Select
                    value={selectedSlotStart}
                    onValueChange={(value) => setSelectedSlotStart(value ?? "")}
                    disabled={!selectedDate}
                  >
                    <SelectTrigger id="reschedule-time">
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

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter showCloseButton>
            <Button
              type="button"
              disabled={submitting || loadingSlots || !!slotError || filteredSlots.length === 0 || !selectedSlotStart}
              onClick={() => void handleSubmit()}
            >
              {submitting ? "Rescheduling..." : "Confirm reschedule"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
