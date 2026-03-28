"use client";

import { useState } from "react";
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

export function RaiseDisputeDialog({
  booking,
  onRaised,
}: {
  booking: Booking;
  onRaised: (bookingId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await apiClient.bookings.raiseDispute(booking.id, { reason: reason.trim() });
      onRaised(booking.id);
      setOpen(false);
      setReason("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not raise this dispute."));
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
        onClick={() => setOpen(true)}
      >
        Raise dispute
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Raise dispute</DialogTitle>
            <DialogDescription>
              Explain what went wrong with this lesson. An admin will review it before funds are fully released.
            </DialogDescription>
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
              placeholder="Describe the issue in enough detail for admin to investigate..."
              className="min-h-32"
            />
          </div>

          <DialogFooter showCloseButton>
            <Button
              type="button"
              disabled={submitting || reason.trim().length < 10}
              onClick={() => void handleSubmit()}
            >
              {submitting ? "Submitting…" : "Submit dispute"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
