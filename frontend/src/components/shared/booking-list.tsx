"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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

export function BookingList() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.bookings.list()
      .then(({ data }) => setBookings(data as Booking[]))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <BookingSkeleton />;

  if (bookings.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4">No bookings yet.</p>
    );
  }

  // Split upcoming vs past
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
            {upcoming.map((b) => <BookingRow key={b.id} booking={b} />)}
          </div>
        </div>
      )}
      {past.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Past</h3>
          <div className="space-y-2">
            {past.slice(0, 5).map((b) => <BookingRow key={b.id} booking={b} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function BookingRow({ booking }: { booking: Booking }) {
  const statusCfg = STATUS_CONFIG[booking.status];
  return (
    <Card>
      <CardContent className="py-3 px-4 flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium">{formatDate(booking.scheduledAt)}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {booking.durationMinutes} min · R{(booking.amountCents / 100).toFixed(2)}
            {booking.isTrial && " · Trial"}
          </p>
        </div>
        <Badge variant={statusCfg.variant} className="shrink-0">
          {statusCfg.label}
        </Badge>
      </CardContent>
    </Card>
  );
}
