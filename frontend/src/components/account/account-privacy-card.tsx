"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { AccountConsent, AccountDeletionStatus } from "@/types";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";

function getErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? fallback;
}

function formatTimestamp(value?: string | null) {
  if (!value) return null;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function AccountPrivacyCard() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const [consents, setConsents] = useState<AccountConsent | null>(null);
  const [deletionStatus, setDeletionStatus] = useState<AccountDeletionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [requestingDeletion, setRequestingDeletion] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [{ data: consentData }, { data: deletionData }] = await Promise.all([
          apiClient.account.getConsents(),
          apiClient.account.getDeletionStatus(),
        ]);
        if (!cancelled) {
          setConsents(consentData);
          setDeletionStatus(deletionData);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(getErrorMessage(err, "Could not load privacy settings."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    if (user) {
      void load();
    }

    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) {
    return null;
  }

  async function handleConsentToggle(field: "marketingEmail" | "marketingSms", checked: boolean) {
    if (!consents) return;
    const next = {
      marketingEmail: field === "marketingEmail" ? checked : consents.marketingEmail.granted,
      marketingSms: field === "marketingSms" ? checked : consents.marketingSms.granted,
    };

    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.account.updateConsents(next);
      setConsents(data);
      setMessage("Marketing consent updated.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not update consent preferences."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDownloadExport() {
    setDownloading(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.account.getDataExport();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `fundaconnect-account-export-${data.exportedAt.slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setMessage("Account data export downloaded.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not download your account export."));
    } finally {
      setDownloading(false);
    }
  }

  async function handleDeleteRequest() {
    const confirmed = window.confirm(
      "This will deactivate your account, cancel future bookings, and schedule anonymisation after the grace period. Continue?"
    );
    if (!confirmed) return;

    setRequestingDeletion(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.account.requestDeletion();
      setDeletionStatus(data);
      setMessage("Account deletion requested. Signing you out…");
      await logout();
      router.replace("/login");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not request account deletion."));
    } finally {
      setRequestingDeletion(false);
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Privacy & Data</CardTitle>
        <CardDescription>
          Download your account data, manage marketing consent, or request account deletion.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {(message || error) && (
          <Alert variant={error ? "destructive" : "default"}>
            <AlertDescription>{error ?? message}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading privacy settings…</p>
        ) : (
          <>
            <div className="space-y-3 rounded-lg border border-border/70 bg-muted/30 p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Required consents</p>
                <p className="text-sm text-muted-foreground">
                  Terms of Service: {consents?.termsOfService.granted ? "Accepted" : "Not accepted"}
                </p>
                <p className="text-sm text-muted-foreground">
                  Privacy Policy: {consents?.privacyPolicy.granted ? "Accepted" : "Not accepted"}
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex items-start gap-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-border"
                    checked={consents?.marketingEmail.granted ?? false}
                    disabled={saving}
                    onChange={(e) => handleConsentToggle("marketingEmail", e.target.checked)}
                  />
                  <span>
                    <Label className="text-sm font-medium">Marketing email</Label>
                    <span className="mt-1 block text-muted-foreground">
                      Receive occasional product updates and marketing by email.
                    </span>
                  </span>
                </label>

                <label className="flex items-start gap-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-border"
                    checked={consents?.marketingSms.granted ?? false}
                    disabled={saving}
                    onChange={(e) => handleConsentToggle("marketingSms", e.target.checked)}
                  />
                  <span>
                    <Label className="text-sm font-medium">Marketing SMS</Label>
                    <span className="mt-1 block text-muted-foreground">
                      Receive occasional product updates and marketing by SMS.
                    </span>
                  </span>
                </label>
              </div>
            </div>

            <div className="rounded-lg border border-border/70 bg-muted/30 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Account data export</p>
                  <p className="text-sm text-muted-foreground">
                    Download a JSON export of your current account data.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleDownloadExport}
                  disabled={downloading}
                >
                  {downloading ? "Preparing…" : "Download export"}
                </Button>
              </div>
            </div>

            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-destructive">Account deletion</p>
                  {deletionStatus?.status === "pendingDeletion" ? (
                    <p className="text-sm text-muted-foreground">
                      Deletion requested on {formatTimestamp(deletionStatus.deletionRequestedAt)}.
                      {" "}Anonymisation is scheduled for {formatTimestamp(deletionStatus.deletionScheduledFor)}.
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      This deactivates your account immediately, cancels future bookings, and schedules anonymisation after the grace period.
                    </p>
                  )}
                </div>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={handleDeleteRequest}
                  disabled={requestingDeletion || deletionStatus?.status === "pendingDeletion"}
                >
                  {requestingDeletion ? "Requesting…" : deletionStatus?.status === "pendingDeletion" ? "Deletion scheduled" : "Request deletion"}
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
