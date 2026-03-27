"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";

interface PayoutItem {
  id: string;
  amountCents: number;
  status: string;
  bankReference: string | null;
  processedAt: string | null;
  createdAt: string;
}

interface EarningsSummary {
  totalEarnedCents: number;
  pendingPayoutCents: number;
  paidOutCents: number;
  payouts: PayoutItem[];
}

const STATUS_BADGE: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  processing: "outline",
  paid: "default",
  failed: "destructive",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function rand(cents: number) {
  return `R${(cents / 100).toFixed(2)}`;
}

export function EarningsSection() {
  const [data, setData] = useState<EarningsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.teachers.getEarnings()
      .then(({ data }) => setData(data as EarningsSummary))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Earned</CardDescription>
            <CardTitle className="text-2xl">{rand(data.totalEarnedCents)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Pending Payout</CardDescription>
            <CardTitle className="text-2xl">{rand(data.pendingPayoutCents)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Paid Out</CardDescription>
            <CardTitle className="text-2xl">{rand(data.paidOutCents)}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {data.payouts.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Payout History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.payouts.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between text-sm border-b pb-2 last:border-0"
                >
                  <div>
                    <span className="font-medium">{rand(p.amountCents)}</span>
                    <span className="text-muted-foreground ml-2">
                      {formatDate(p.createdAt)}
                    </span>
                    {p.bankReference && (
                      <span className="text-muted-foreground ml-2 text-xs">
                        Ref: {p.bankReference}
                      </span>
                    )}
                  </div>
                  <Badge variant={STATUS_BADGE[p.status] ?? "secondary"}>
                    {p.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
