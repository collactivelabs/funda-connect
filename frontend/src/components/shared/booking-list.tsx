"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LeaveReviewDialog } from "@/components/parent/leave-review-dialog";
import { CompleteLessonDialog } from "@/components/shared/complete-lesson-dialog";
import { RaiseDisputeDialog } from "@/components/shared/raise-dispute-dialog";
import { RescheduleBookingDialog } from "@/components/shared/reschedule-booking-dialog";
import { apiClient } from "@/lib/api";
import type { Booking, BookingStatus } from "@/types";

const STATUS_CONFIG: Record<BookingStatus, { label: string; variant: "default" | "secondary" | "outline" | "destructive" }> = {
  pending_payment: { label: "Awaiting payment", variant: "secondary" },
  confirmed: { label: "Confirmed", variant: "default" },
  in_progress: { label: "In progress", variant: "default" },
  completed: { label: "Completed", variant: "outline" },
  disputed: { label: "Disputed", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "destructive" },
  expired: { label: "Payment expired", variant: "destructive" },
  reviewed: { label: "Reviewed", variant: "outline" },
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-ZA", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function BookingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}
    </div>
  );
}

interface Props {
  role?: "parent" | "teacher";
}

export function BookingList({ role }: Props) {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    apiClient.bookings.list()
      .then(({ data }: { data: Booking[] }) => setBookings(data))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setNow(new Date());
    }, 30_000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  function markReviewed(bookingId: string) {
    setBookings((prev) =>
      prev.map((b) => (b.id === bookingId ? { ...b, status: "reviewed" as BookingStatus } : b))
    );
  }

  function updateBooking(bookingId: string, patch: Partial<Booking>) {
    setBookings((prev) =>
      prev.map((b) => (b.id === bookingId ? { ...b, ...patch } : b))
    );
  }

  function markDisputed(bookingId: string) {
    updateBooking(bookingId, { status: "disputed" });
  }

  function cancelSeries(cancelledIds: string[]) {
    setBookings((prev) =>
      prev.map((b) =>
        cancelledIds.includes(b.id)
          ? { ...b, status: "cancelled" as BookingStatus }
          : b
      )
    );
  }

  if (loading) return <BookingSkeleton />;

  if (bookings.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4">No bookings yet.</p>
    );
  }

  const terminalStatuses = new Set<BookingStatus>(["completed", "reviewed", "cancelled", "expired"]);
  const upcoming = bookings.filter(
    (booking) => {
      const lessonEnd = new Date(new Date(booking.scheduledAt).getTime() + booking.durationMinutes * 60_000);
      return !terminalStatuses.has(booking.status) && lessonEnd >= now;
    }
  );
  const past = bookings.filter(
    (booking) => {
      const lessonEnd = new Date(new Date(booking.scheduledAt).getTime() + booking.durationMinutes * 60_000);
      return terminalStatuses.has(booking.status) || lessonEnd < now;
    }
  );

  return (
    <div className="space-y-6">
      {upcoming.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Upcoming</h3>
          <div className="space-y-2">
            {upcoming.map((b) => (
              <BookingRow key={b.id} booking={b} role={role} now={now} onReviewed={markReviewed} onDisputed={markDisputed} onUpdated={updateBooking} onSeriesCancelled={cancelSeries} />
            ))}
          </div>
        </div>
      )}
      {past.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Past</h3>
          <div className="space-y-2">
            {past.slice(0, 5).map((b) => (
              <BookingRow key={b.id} booking={b} role={role} now={now} onReviewed={markReviewed} onDisputed={markDisputed} onUpdated={updateBooking} onSeriesCancelled={cancelSeries} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BookingRow({
  booking,
  role,
  now,
  onReviewed,
  onDisputed,
  onUpdated,
  onSeriesCancelled,
}: {
  booking: Booking;
  role?: "parent" | "teacher";
  now: Date;
  onReviewed: (id: string) => void;
  onDisputed: (id: string) => void;
  onUpdated: (id: string, patch: Partial<Booking>) => void;
  onSeriesCancelled: (ids: string[]) => void;
}) {
  const [acting, setActing] = useState(false);
  const statusCfg = STATUS_CONFIG[booking.status];
  const subjectName = booking.subject?.name;
  const learnerName = booking.learner
    ? `${booking.learner.firstName} ${booking.learner.lastName}`
    : null;

  const lessonStart = new Date(booking.scheduledAt);
  const lessonEnd = new Date(lessonStart.getTime() + booking.durationMinutes * 60_000);
  // Show join button from 10 min before start until lesson end
  const joinWindowOpen = new Date(lessonStart.getTime() - 10 * 60_000) <= now && now <= lessonEnd;
  const canJoin = booking.videoRoomUrl && joinWindowOpen && booking.status === "confirmed";
  const canMarkComplete = role === "teacher" && booking.status === "confirmed" && now >= lessonStart;
  const canReview = role === "parent" && booking.status === "completed";
  const canReschedule =
    (role === "parent" || role === "teacher") &&
    booking.status === "confirmed" &&
    now < lessonStart;
  const canRaiseDispute =
    (role === "parent" || role === "teacher") &&
    now >= lessonStart &&
    ["confirmed", "in_progress", "completed", "reviewed"].includes(booking.status);
  // A child booking has a recurringBookingId pointing to its root
  const isChildRecurring = booking.isRecurring && !!booking.recurringBookingId;

  return (
    <Card>
      <CardContent className="py-3 px-4 flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium">{formatDate(booking.scheduledAt)}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {[
              subjectName,
              learnerName,
              `${booking.durationMinutes} min`,
              `R${(booking.amountCents / 100).toFixed(2)}`,
              booking.isTrial ? "Trial" : null,
              booking.isRecurring ? (isChildRecurring ? "Recurring" : "Recurring (root)") : null,
            ].filter(Boolean).join(" · ")}
          </p>
          {booking.lessonNotes && (
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
              {booking.lessonNotes}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {canJoin && (
            <a
              href={booking.videoRoomUrl!}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Join lesson
            </a>
          )}
          {!canJoin && booking.videoRoomUrl && booking.status === "confirmed" && (
            <a
              href={booking.videoRoomUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground underline underline-offset-2"
            >
              Room link
            </a>
          )}
          {canReview && (
            <LeaveReviewDialog
              bookingId={booking.id}
              onReviewed={() => onReviewed(booking.id)}
            />
          )}
          {canReschedule && (
            <RescheduleBookingDialog
              booking={booking}
              onRescheduled={(patch) => onUpdated(booking.id, patch)}
            />
          )}
          {canRaiseDispute && (
            <RaiseDisputeDialog
              booking={booking}
              onRaised={onDisputed}
            />
          )}
          {canMarkComplete && (
            <CompleteLessonDialog
              booking={booking}
              onCompleted={(nextBooking) => onUpdated(booking.id, nextBooking)}
            />
          )}
          {booking.isRecurring && booking.status === "confirmed" && (
            <Button
              size="sm"
              variant="destructive"
              className="text-xs h-7"
              disabled={acting}
              onClick={async () => {
                if (!confirm("Cancel all future lessons in this recurring series?")) return;
                setActing(true);
                try {
                  const { data } = await apiClient.bookings.cancelSeries(booking.id, {
                    reason: "Cancelled by user",
                  });
                  const ids = (data as Booking[]).map((b) => b.id);
                  onSeriesCancelled(ids);
                } catch { /* ignore */ }
                setActing(false);
              }}
            >
              Cancel series
            </Button>
          )}
          <Badge variant={statusCfg.variant} className="text-xs">
            {statusCfg.label}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}
