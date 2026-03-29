"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth.store";

function getSafeRedirectPath(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return null;
  }
  return value;
}

function mapGoogleError(code: string | null, flow: string | null): { message: string; href: string; cta: string } {
  switch (code) {
    case "cancelled":
      return {
        message: "Google sign-in was cancelled before it could finish.",
        href: flow === "register" ? "/register" : "/login",
        cta: flow === "register" ? "Back to registration" : "Back to sign in",
      };
    case "expired_state":
      return {
        message: "This Google sign-in attempt expired. Please start again.",
        href: flow === "register" ? "/register" : "/login",
        cta: flow === "register" ? "Try registration again" : "Try sign in again",
      };
    case "email_unverified":
      return {
        message: "Your Google account email address is not verified yet.",
        href: flow === "register" ? "/register" : "/login",
        cta: flow === "register" ? "Back to registration" : "Back to sign in",
      };
    case "already_registered":
      return {
        message: "That email is already registered. Please sign in instead.",
        href: "/login",
        cta: "Go to sign in",
      };
    case "account_not_found":
      return {
        message: "No account exists for this Google email yet. Please create one first.",
        href: "/register",
        cta: "Go to registration",
      };
    case "account_disabled":
      return {
        message: "This account has been disabled. Please contact support if you need help.",
        href: "/login",
        cta: "Back to sign in",
      };
    case "invalid_callback":
      return {
        message: "Google returned an incomplete sign-in response.",
        href: flow === "register" ? "/register" : "/login",
        cta: "Try again",
      };
    default:
      return {
        message: "We couldn't complete Google sign-in right now. Please try again.",
        href: flow === "register" ? "/register" : "/login",
        cta: "Try again",
      };
  }
}

export function GoogleOAuthComplete() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, setAccessToken } = useAuthStore();
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const flow = searchParams.get("flow");
  const errorCode = searchParams.get("error");
  const mappedParamError = errorCode ? mapGoogleError(errorCode, flow) : null;

  useEffect(() => {
    const redirectPath = getSafeRedirectPath(searchParams.get("redirect"));

    if (mappedParamError) {
      return;
    }

    let cancelled = false;

    apiClient.auth.refreshSession()
      .then(({ data }) => {
        if (cancelled) {
          return;
        }
        setAccessToken(data.accessToken);
        setUser(data.user);
        const destination = redirectPath ?? (data.user.role === "admin" ? "/admin" : `/${data.user.role}`);
        router.replace(destination);
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setRuntimeError(detail ?? "We couldn't finish signing you in. Please try again.");
      });

    return () => {
      cancelled = true;
    };
  }, [mappedParamError, router, searchParams, setAccessToken, setUser]);

  const fallback = mappedParamError ?? mapGoogleError(null, flow);
  const error = runtimeError ?? mappedParamError?.message ?? null;

  if (error) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Link
          href={fallback.href}
          className={cn(buttonVariants({ variant: "default" }), "flex w-full justify-center")}
        >
          {fallback.cta}
        </Link>
      </div>
    );
  }

  return <p className="text-sm text-muted-foreground">Finishing your Google sign-in…</p>;
}
