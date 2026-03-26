"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function PaymentStatusBanner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [dismissed, setDismissed] = useState(false);

  const status = searchParams.get("status");
  const bookingId = searchParams.get("booking");

  // Remove query params from URL without re-render
  useEffect(() => {
    if ((status === "success" || status === "cancelled") && bookingId) {
      const url = new URL(window.location.href);
      url.searchParams.delete("status");
      url.searchParams.delete("booking");
      router.replace(url.pathname + url.search, { scroll: false });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!status || !bookingId || dismissed) return null;

  if (status === "success") {
    return (
      <Alert className="border-green-500/50 bg-green-500/10">
        <AlertDescription className="flex items-center justify-between gap-4">
          <span>
            Payment successful! Your lesson is confirmed. Check your lessons below.
          </span>
          <Button variant="ghost" size="sm" className="shrink-0" onClick={() => setDismissed(true)}>
            Dismiss
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (status === "cancelled") {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between gap-4">
          <span>Payment was cancelled. Your booking has not been confirmed.</span>
          <Button variant="ghost" size="sm" className="shrink-0 text-destructive-foreground" onClick={() => setDismissed(true)}>
            Dismiss
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return null;
}
