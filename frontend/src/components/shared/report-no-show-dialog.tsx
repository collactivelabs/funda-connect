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
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/api";
import type { Booking } from "@/types";

function getErrorMessage(error: unknown, fallback: string) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;
}

export function ReportNoShowDialog({
  booking,
  role,
  onReported,
}: {
  booking: Booking;
  role: "parent" | "teacher";
  onReported: (booking: Booking) => void;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const copy = useMemo(() => {
    if (role === "parent") {
      return {
        title: "Report teacher no-show",
        button: "Teacher no-show",
        description:
          "Use this if the teacher still has not arrived after the grace period. A full refund will be queued for review.",
        placeholder: "Add any context that will help us understand what happened...",
      };
    }

    return {
      title: "Report learner no-show",
      button: "Learner no-show",
      description:
        "Use this if the learner still has not arrived after the grace period. The lesson will be marked as a parent no-show.",
      placeholder: "Add any context that will help us understand what happened...",
    };
  }, [role]);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);

    try {
      const { data } = await apiClient.bookings.reportNoShow(booking.id, {
        reason: reason.trim() || null,
      });
      onReported(data as Booking);
      setOpen(false);
      setReason("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not report this no-show."));
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
        className="h-7 text-xs"
        onClick={() => setOpen(true)}
      >
        {copy.button}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{copy.title}</DialogTitle>
            <DialogDescription>{copy.description}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={copy.placeholder}
              className="min-h-28"
            />
          </div>

          <DialogFooter showCloseButton>
            <Button type="button" disabled={submitting} onClick={() => void handleSubmit()}>
              {submitting ? "Submitting…" : "Confirm no-show"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
