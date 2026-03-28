"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api";

export function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = useMemo(() => searchParams.get("token") ?? "", [searchParams]);
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const { data } = await apiClient.auth.resetPassword({
        token,
        new_password: newPassword,
      });
      setMessage(data.message as string);
      setTimeout(() => router.push("/login"), 1200);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Unable to reset password. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Password reset link is missing or invalid.</AlertDescription>
      </Alert>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
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

      <div className="space-y-2">
        <Label htmlFor="newPassword">New password</Label>
        <Input
          id="newPassword"
          type="password"
          placeholder="Min. 8 characters"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          minLength={8}
          autoComplete="new-password"
        />
      </div>

      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? "Updating password…" : "Reset password"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Back to{" "}
        <Link href="/login" className="underline underline-offset-4 hover:text-foreground">
          sign in
        </Link>
      </p>
    </form>
  );
}
