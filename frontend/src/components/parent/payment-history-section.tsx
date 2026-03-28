"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";
import type { ParentPaymentHistoryItem, ParentPaymentHistorySummary, PaymentStatus } from "@/types";

const STATUS_BADGE: Record<PaymentStatus, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  complete: "default",
  failed: "destructive",
  refunded: "outline",
  partially_refunded: "outline",
  cancelled: "destructive",
};

const REFUND_BADGE = {
  pending: "secondary",
  processing: "outline",
  refunded: "default",
  failed: "destructive",
  cancelled: "destructive",
} as const;

function formatRand(cents: number) {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-ZA", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function PaymentHistorySkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        {[1, 2, 3, 4].map((item) => (
          <Skeleton key={item} className="h-24 w-full" />
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function PaymentRow({ payment }: { payment: ParentPaymentHistoryItem }) {
  return (
    <div className="flex flex-col gap-3 border-b border-border/60 py-3 last:border-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{formatRand(payment.amountCents)}</span>
          <Badge variant={STATUS_BADGE[payment.status] ?? "secondary"}>
            {payment.status}
          </Badge>
          {payment.refundStatus && (
            <Badge variant={REFUND_BADGE[payment.refundStatus] ?? "secondary"}>
              refund {payment.refundStatus}
            </Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {payment.subjectName} with {payment.teacherName}
        </p>
        <p className="text-sm text-muted-foreground">
          Learner: {payment.learnerName}
          {" · "}
          {payment.isSeries ? `Series starts ${formatDate(payment.scheduledAt)}` : `Lesson: ${formatDate(payment.scheduledAt)}`}
        </p>
        <p className="text-xs text-muted-foreground">
          {payment.isSeries ? `Prepaid weekly series · ${payment.seriesLessons} lessons` : `Booking status: ${payment.bookingStatus}`}
          {payment.gatewayPaymentId ? ` · Ref: ${payment.gatewayPaymentId}` : ""}
        </p>
        {payment.refundStatus && payment.refundAmountCents > 0 && (
          <p className="text-xs text-muted-foreground">
            Refund amount: {formatRand(payment.refundAmountCents)}
            {payment.refundProcessedAt
              ? ` · processed ${formatDate(payment.refundProcessedAt)}`
              : payment.refundRequestedAt
                ? ` · requested ${formatDate(payment.refundRequestedAt)}`
                : ""}
          </p>
        )}
      </div>
      <div className="text-sm text-muted-foreground sm:text-right">
        <p>{payment.paidAt ? `Paid ${formatDate(payment.paidAt)}` : `Created ${formatDate(payment.createdAt)}`}</p>
        <p className="text-xs uppercase tracking-wide">{payment.gateway}</p>
        {payment.status !== "pending" && payment.status !== "failed" && payment.status !== "cancelled" && (
          <Link
            href={`/parent/payments/${payment.id}/receipt`}
            className={buttonVariants({ variant: "outline" }) + " mt-2 h-8 px-3 text-xs"}
          >
            View receipt
          </Link>
        )}
      </div>
    </div>
  );
}

export function PaymentHistorySection() {
  const [summary, setSummary] = useState<ParentPaymentHistorySummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.parents.getPayments()
      .then(({ data }) => setSummary(data))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <PaymentHistorySkeleton />;
  }

  if (!summary) {
    return null;
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Payments</h2>
        <p className="text-sm text-muted-foreground">Track what has been paid, what is pending, and what was refunded.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completed Payments</CardDescription>
            <CardTitle className="text-2xl">{formatRand(summary.completedPaymentsCents)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Pending Payments</CardDescription>
            <CardTitle className="text-2xl">{formatRand(summary.pendingPaymentsCents)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Refunded Payments</CardDescription>
            <CardTitle className="text-2xl">{formatRand(summary.refundedPaymentsCents)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Refunds Pending</CardDescription>
            <CardTitle className="text-2xl">{formatRand(summary.refundPendingCents)}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Payment History</CardTitle>
          <CardDescription>Each payment is tied back to the booking, learner, and teacher.</CardDescription>
        </CardHeader>
        <CardContent>
          {summary.payments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No payment history yet.</p>
          ) : (
            <div className="space-y-1">
              {summary.payments.map((payment) => (
                <PaymentRow key={payment.id} payment={payment} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
