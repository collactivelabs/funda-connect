"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ParentPaymentReceipt } from "@/types";

function formatRand(cents: number) {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("en-ZA", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ReceiptSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-40" />
      <Skeleton className="h-[32rem] w-full" />
    </div>
  );
}

function DetailRow({
  label,
  value,
  emphasize = false,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border/60 py-3 last:border-0">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={cn("text-right text-sm", emphasize && "font-medium text-foreground")}>{value}</dd>
    </div>
  );
}

export function PaymentReceiptPage({ paymentId }: { paymentId: string }) {
  const [receipt, setReceipt] = useState<ParentPaymentReceipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    apiClient.parents.getPaymentReceipt(paymentId)
      .then(({ data }) => {
        if (!cancelled) {
          setReceipt(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
          setError(detail ?? "Could not load this receipt.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [paymentId]);

  if (loading) {
    return <ReceiptSkeleton />;
  }

  if (!receipt) {
    return (
      <div className="space-y-4">
        <Link href="/parent" className={buttonVariants({ variant: "outline" })}>
          Back to dashboard
        </Link>
        <Card>
          <CardContent className="py-10 text-sm text-muted-foreground">
            {error ?? "Receipt not found."}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link href="/parent" className={buttonVariants({ variant: "outline" })}>
          Back to dashboard
        </Link>
        <Button type="button" onClick={() => window.print()}>
          Print receipt
        </Button>
      </div>

      <Card className="mx-auto max-w-4xl">
        <CardHeader className="border-b border-border/60">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <CardTitle className="text-2xl">Payment Receipt</CardTitle>
              <CardDescription>FundaConnect lesson payment confirmation</CardDescription>
            </div>
            <div className="space-y-1 text-sm sm:text-right">
              <p className="font-medium">{receipt.receiptReference}</p>
              <p className="text-muted-foreground">Issued {formatDate(receipt.issuedAt)}</p>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-8 py-6">
          <div className="grid gap-4 md:grid-cols-2">
            <Card size="sm" className="bg-muted/20">
              <CardHeader>
                <CardTitle>Billed To</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>{receipt.parentName}</p>
                <p className="text-muted-foreground">{receipt.parentEmail}</p>
              </CardContent>
            </Card>

            <Card size="sm" className="bg-muted/20">
              <CardHeader>
                <CardTitle>Lesson</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>{receipt.subjectName}</p>
                <p className="text-muted-foreground">Teacher: {receipt.teacherName}</p>
                <p className="text-muted-foreground">Learner: {receipt.learnerName}</p>
                <p className="text-muted-foreground">
                  {receipt.isSeries
                    ? `Series starts: ${formatDate(receipt.scheduledAt)}`
                    : `Scheduled: ${formatDate(receipt.scheduledAt)}`}
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <div className="space-y-2">
              <h2 className="text-base font-semibold">Payment details</h2>
              <dl>
                <DetailRow label="Gateway" value={receipt.paymentGateway.toUpperCase()} />
                <DetailRow label="Gateway reference" value={receipt.paymentGatewayReference ?? "—"} />
                <DetailRow label="Payment status" value={receipt.paymentStatus} />
                <DetailRow label="Booking reference" value={receipt.bookingId.slice(0, 8).toUpperCase()} />
                <DetailRow label="Duration" value={`${receipt.durationMinutes} minutes`} />
                <DetailRow
                  label="Lesson type"
                  value={
                    receipt.isSeries
                      ? `Prepaid weekly series (${receipt.seriesLessons} lessons)`
                      : (receipt.isTrial ? "Trial lesson" : "Standard lesson")
                  }
                />
              </dl>
            </div>

            <div className="space-y-2">
              <h2 className="text-base font-semibold">Summary</h2>
              <Card size="sm" className="bg-muted/20">
                <CardContent className="pt-3">
                  <dl>
                    <DetailRow label="Amount charged" value={formatRand(receipt.amountCents)} />
                    <DetailRow label="Refunded" value={formatRand(receipt.refundAmountCents)} />
                    <DetailRow label="Net paid" value={formatRand(receipt.netPaidCents)} emphasize />
                  </dl>
                </CardContent>
              </Card>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
