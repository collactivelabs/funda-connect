"use client";

import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";

export function VerifyEmailBanner() {
  const { user } = useAuthStore();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!user || user.emailVerified) {
    return null;
  }
  const email = user.email;

  async function handleResend() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.auth.requestEmailVerification({ email });
      setMessage(data.message as string);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Could not resend verification email.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Alert className="mb-6">
      <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span>
          Your email address is not verified yet. Check your inbox for the verification link.
          {message ? ` ${message}` : ""}
          {error ? ` ${error}` : ""}
        </span>
        <Button type="button" variant="outline" size="sm" onClick={handleResend} disabled={loading}>
          {loading ? "Sending…" : "Resend email"}
        </Button>
      </AlertDescription>
    </Alert>
  );
}
