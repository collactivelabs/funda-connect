"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";
import { useRouter } from "next/navigation";

// ── Types ─────────────────────────────────────────────────────

interface Stats {
  total_teachers: number;
  pending_verification: number;
  verified_teachers: number;
  total_parents: number;
  total_bookings: number;
  confirmed_bookings: number;
  total_revenue_cents: number;
  pending_payouts_cents: number;
}

interface AdminTeacher {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  verification_status: string;
  is_listed: boolean;
  is_premium: boolean;
  total_lessons: number;
  hourly_rate_cents: number | null;
  province: string | null;
  subject_count: number;
  document_count: number;
}

interface AdminPayout {
  id: string;
  teacher_id: string;
  teacher_name: string;
  amount_cents: number;
  status: string;
  created_at: string;
}

// ── Helpers ───────────────────────────────────────────────────

function formatRand(cents: number) {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

const VERIFICATION_BADGE: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  under_review: "secondary",
  verified: "default",
  rejected: "destructive",
  suspended: "destructive",
};

const PAYOUT_BADGE: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  processing: "secondary",
  paid: "default",
  failed: "destructive",
};

// ── Stats Cards ───────────────────────────────────────────────

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold mt-1">{value}</p>
      </CardContent>
    </Card>
  );
}

// ── Main Component ────────────────────────────────────────────

export default function AdminPage() {
  const { user } = useAuthStore();
  const router = useRouter();

  const [stats, setStats] = useState<Stats | null>(null);
  const [teachers, setTeachers] = useState<AdminTeacher[]>([]);
  const [payouts, setPayouts] = useState<AdminPayout[]>([]);
  const [teacherFilter, setTeacherFilter] = useState("pending");
  const [payoutFilter, setPayoutFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Guard: admin only
  useEffect(() => {
    if (user && user.role !== "admin") router.replace("/");
  }, [user, router]);

  useEffect(() => {
    apiClient.admin.getStats()
      .then(({ data }) => setStats(data as Stats))
      .catch(() => null);
  }, []);

  useEffect(() => {
    setLoading(true);
    apiClient.admin
      .listTeachers(teacherFilter ? { verification_status: teacherFilter } : undefined)
      .then(({ data }) => setTeachers(data as AdminTeacher[]))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [teacherFilter]);

  useEffect(() => {
    apiClient.admin
      .listPayouts(payoutFilter ? { payout_status: payoutFilter } : undefined)
      .then(({ data }) => setPayouts(data as AdminPayout[]))
      .catch(() => null);
  }, [payoutFilter]);

  async function handleVerify(teacherId: string, action: "verify" | "reject" | "suspend") {
    setActionLoading(`verify-${teacherId}-${action}`);
    try {
      await apiClient.admin.verifyTeacher(teacherId, { action });
      setTeachers((prev) =>
        prev.map((t) =>
          t.id === teacherId
            ? {
                ...t,
                verification_status: action === "verify" ? "verified" : action === "reject" ? "rejected" : "suspended",
                is_listed: action === "verify",
              }
            : t
        )
      );
      // refresh stats
      apiClient.admin.getStats().then(({ data }) => setStats(data as Stats)).catch(() => null);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleTogglePremium(teacherId: string) {
    setActionLoading(`premium-${teacherId}`);
    try {
      const { data } = await apiClient.admin.togglePremium(teacherId);
      setTeachers((prev) =>
        prev.map((t) => (t.id === teacherId ? { ...t, is_premium: (data as { is_premium: boolean }).is_premium } : t))
      );
    } finally {
      setActionLoading(null);
    }
  }

  async function handlePayoutStatus(payoutId: string, newStatus: string) {
    setActionLoading(`payout-${payoutId}`);
    try {
      await apiClient.admin.updatePayout(payoutId, { status: newStatus });
      setPayouts((prev) =>
        prev.map((p) => (p.id === payoutId ? { ...p, status: newStatus } : p))
      );
      apiClient.admin.getStats().then(({ data }) => setStats(data as Stats)).catch(() => null);
    } finally {
      setActionLoading(null);
    }
  }

  if (user && user.role !== "admin") return null;

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">Platform overview and management</p>
      </div>

      {/* Stats */}
      {stats ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Total Teachers" value={stats.total_teachers} />
          <StatCard label="Pending Verification" value={stats.pending_verification} />
          <StatCard label="Verified Teachers" value={stats.verified_teachers} />
          <StatCard label="Total Parents" value={stats.total_parents} />
          <StatCard label="Total Bookings" value={stats.total_bookings} />
          <StatCard label="Confirmed Bookings" value={stats.confirmed_bookings} />
          <StatCard label="Total Revenue" value={formatRand(stats.total_revenue_cents)} />
          <StatCard label="Pending Payouts" value={formatRand(stats.pending_payouts_cents)} />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}

      {/* Teacher verification queue */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base font-semibold">Teachers</CardTitle>
          <Select value={teacherFilter} onValueChange={(v) => setTeacherFilter(v ?? "")}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="under_review">Under review</SelectItem>
              <SelectItem value="verified">Verified</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
              <SelectItem value="suspended">Suspended</SelectItem>
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : teachers.length === 0 ? (
            <p className="text-sm text-muted-foreground p-6">No teachers found.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Rate</TableHead>
                  <TableHead className="text-right">Docs</TableHead>
                  <TableHead className="text-right">Subjects</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {teachers.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium">
                      {t.first_name} {t.last_name}
                      {t.is_premium && (
                        <Badge variant="outline" className="ml-2 text-xs">Premium</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{t.email}</TableCell>
                    <TableCell>
                      <Badge variant={VERIFICATION_BADGE[t.verification_status] ?? "outline"}>
                        {t.verification_status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {t.hourly_rate_cents ? formatRand(t.hourly_rate_cents) + "/hr" : "—"}
                    </TableCell>
                    <TableCell className="text-right text-sm">{t.document_count}</TableCell>
                    <TableCell className="text-right text-sm">{t.subject_count}</TableCell>
                    <TableCell>
                      <div className="flex gap-1 justify-end flex-wrap">
                        {t.verification_status !== "verified" && (
                          <Button
                            size="sm"
                            variant="default"
                            disabled={actionLoading === `verify-${t.id}-verify`}
                            onClick={() => handleVerify(t.id, "verify")}
                          >
                            Verify
                          </Button>
                        )}
                        {t.verification_status !== "rejected" && (
                          <Button
                            size="sm"
                            variant="destructive"
                            disabled={actionLoading === `verify-${t.id}-reject`}
                            onClick={() => handleVerify(t.id, "reject")}
                          >
                            Reject
                          </Button>
                        )}
                        {t.verification_status !== "suspended" && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={actionLoading === `verify-${t.id}-suspend`}
                            onClick={() => handleVerify(t.id, "suspend")}
                          >
                            Suspend
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={actionLoading === `premium-${t.id}`}
                          onClick={() => handleTogglePremium(t.id)}
                        >
                          {t.is_premium ? "Unpremium" : "Premium"}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Payouts */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base font-semibold">Payouts</CardTitle>
          <Select value={payoutFilter} onValueChange={(v) => setPayoutFilter(v ?? "")}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="paid">Paid</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent className="p-0">
          {payouts.length === 0 ? (
            <p className="text-sm text-muted-foreground p-6">No payouts found.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Teacher</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {payouts.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.teacher_name}</TableCell>
                    <TableCell className="text-right">{formatRand(p.amount_cents)}</TableCell>
                    <TableCell>
                      <Badge variant={PAYOUT_BADGE[p.status] ?? "outline"}>{p.status}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(p.created_at).toLocaleDateString("en-ZA")}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 justify-end">
                        {p.status === "pending" && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={actionLoading === `payout-${p.id}`}
                            onClick={() => handlePayoutStatus(p.id, "processing")}
                          >
                            Mark Processing
                          </Button>
                        )}
                        {p.status === "processing" && (
                          <>
                            <Button
                              size="sm"
                              variant="default"
                              disabled={actionLoading === `payout-${p.id}`}
                              onClick={() => handlePayoutStatus(p.id, "paid")}
                            >
                              Mark Paid
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={actionLoading === `payout-${p.id}`}
                              onClick={() => handlePayoutStatus(p.id, "failed")}
                            >
                              Mark Failed
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
