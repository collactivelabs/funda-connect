"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";

export function VerifyEmailForm() {
  const searchParams = useSearchParams();
  const token = useMemo(() => searchParams.get("token") ?? "", [searchParams]);
  const { user, setUser } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;

    apiClient.auth.verifyEmail({ token })
      .then(({ data }) => {
        if (cancelled) return;
        setMessage(data.message as string);
        if (user) {
          setUser({ ...user, emailVerified: true });
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(detail ?? "Unable to verify email.");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [setUser, token, user]);

  if (!token) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Verification link is missing or invalid.</AlertDescription>
      </Alert>
    );
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Verifying your email…</p>;
  }

  const nextHref = user ? `/${user.role === "admin" ? "admin" : user.role}` : "/login";

  return (
    <div className="space-y-4">
      {message && (
        <Alert>
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Link
        href={nextHref}
        className={cn(buttonVariants({ variant: "default" }), "flex w-full justify-center")}
      >
        {user ? "Continue to dashboard" : "Go to sign in"}
      </Link>
    </div>
  );
}
