"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LeaveReviewDialog } from "@/components/parent/leave-review-dialog";
import { apiClient } from "@/lib/api";
import type { Booking, BookingStatus } from "@/types";

const STATUS_CONFIG: Record<BookingStatus, { label: string; variant: "default" | "secondary" | "outline" | "destructive" }> = {
  pending_payment: { label: "Awaiting payment", variant: "secondary" },
  confirmed: { label: "Confirmed", variant: "default" },
  in_progress: { label: "In progress", variant: "default" },
  completed: { label: "Completed", variant: "outline" },
  cancelled: { label: "Cancelled", variant: "destructive" },
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

  useEffect(() => {
    apiClient.bookings.list()
      .then(({ data }) => setBookings(data as Booking[]))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  function markReviewed(bookingId: string) {
    setBookings((prev) =>
      prev.map((b) => (b.id === bookingId ? { ...b, status: "reviewed" as BookingStatus } : b))
    );
  }

  if (loading) return <BookingSkeleton />;

  if (bookings.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4">No bookings yet.</p>
    );
  }

  const now = new Date();
  const upcoming = bookings.filter(
    (b) => new Date(b.scheduledAt) >= now && b.status !== "cancelled"
  );
  const past = bookings.filter(
    (b) => new Date(b.scheduledAt) < now || b.status === "cancelled"
  );

  return (
    <div className="space-y-6">
      {upcoming.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Upcoming</h3>
          <div className="space-y-2">
            {upcoming.map((b) => (
              <BookingRow key={b.id} booking={b} role={role} onReviewed={markReviewed} />
            ))}
          </div>
        </div>
      )}
      {past.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Past</h3>
          <div className="space-y-2">
            {past.slice(0, 5).map((b) => (
              <BookingRow key={b.id} booking={b} role={role} onReviewed={markReviewed} />
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
  onReviewed,
}: {
  booking: Booking;
  role?: "parent" | "teacher";
  onReviewed: (id: string) => void;
}) {
  const statusCfg = STATUS_CONFIG[booking.status];
  const subjectName = booking.subject?.name;
  const learnerName = booking.learner
    ? `${booking.learner.firstName} ${booking.learner.lastName}`
    : null;

  const now = new Date();
  const lessonStart = new Date(booking.scheduledAt);
  const lessonEnd = new Date(lessonStart.getTime() + booking.durationMinutes * 60_000);
  // Show join button from 10 min before start until lesson end
  const joinWindowOpen = new Date(lessonStart.getTime() - 10 * 60_000) <= now && now <= lessonEnd;
  const canJoin = booking.videoRoomUrl && joinWindowOpen && booking.status === "confirmed";
  const canReview = role === "parent" && booking.status === "completed";
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
          <Badge variant={statusCfg.variant} className="text-xs">
            {statusCfg.label}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}
