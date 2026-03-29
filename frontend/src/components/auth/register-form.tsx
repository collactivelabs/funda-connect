"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { GoogleAuthButton } from "@/components/auth/google-auth-button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";
import type { AuthResponse, GoogleOAuthStartResponse } from "@/types";

function getSafeRedirectPath(value: string | null): string | undefined {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return undefined;
  }
  return value;
}

export function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { setUser, setAccessToken } = useAuthStore();

  const initialRole: "parent" | "teacher" = params.get("role") === "teacher" ? "teacher" : "parent";
  const redirectPath = getSafeRedirectPath(params.get("redirect"));
  const [role, setRole] = useState<"parent" | "teacher">(initialRole);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacyPolicy, setAcceptPrivacyPolicy] = useState(false);
  const [marketingEmail, setMarketingEmail] = useState(false);
  const [marketingSms, setMarketingSms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await apiClient.auth.register({
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        role,
        phone: phone || undefined,
        accept_terms: acceptTerms,
        accept_privacy_policy: acceptPrivacyPolicy,
        marketing_email: marketingEmail,
        marketing_sms: marketingSms,
      }) as { data: AuthResponse };
      setAccessToken(data.accessToken);
      setUser(data.user);
      router.push(data.user.role === "teacher" ? "/teacher" : "/parent");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleRegistration() {
    if (!acceptTerms) {
      setError("Please accept the Terms of Service before continuing with Google.");
      return;
    }
    if (!acceptPrivacyPolicy) {
      setError("Please accept the Privacy Policy before continuing with Google.");
      return;
    }

    setError(null);
    setGoogleLoading(true);
    try {
      const { data } = await apiClient.auth.startGoogle({
        flow: "register",
        role,
        redirect_path: redirectPath,
        accept_terms: acceptTerms,
        accept_privacy_policy: acceptPrivacyPolicy,
        marketing_email: marketingEmail,
        marketing_sms: marketingSms,
      }) as { data: GoogleOAuthStartResponse };
      window.location.assign(data.authorizationUrl);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Google sign-up is unavailable right now. Please try again.");
      setGoogleLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Tabs value={role} onValueChange={(v) => setRole(v as "parent" | "teacher")}>
        <TabsList className="w-full">
          <TabsTrigger value="parent" className="flex-1">
            I&apos;m a Parent
          </TabsTrigger>
          <TabsTrigger value="teacher" className="flex-1">
            I&apos;m a Teacher
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="firstName">First name</Label>
          <Input
            id="firstName"
            placeholder="Sipho"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
            autoComplete="given-name"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="lastName">Last name</Label>
          <Input
            id="lastName"
            placeholder="Dlamini"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
            autoComplete="family-name"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="phone">
          Phone <span className="text-muted-foreground">(optional)</span>
        </Label>
        <Input
          id="phone"
          type="tel"
          placeholder="+27 82 000 0000"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          autoComplete="tel"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          placeholder="Min. 8 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          autoComplete="new-password"
        />
      </div>

      <div className="space-y-3 rounded-lg border border-border/70 bg-muted/30 p-4">
        <label className="flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-border"
            checked={acceptTerms}
            onChange={(e) => setAcceptTerms(e.target.checked)}
            required
          />
          <span>
            I agree to the <span className="font-medium text-foreground">Terms of Service</span>.
          </span>
        </label>

        <label className="flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-border"
            checked={acceptPrivacyPolicy}
            onChange={(e) => setAcceptPrivacyPolicy(e.target.checked)}
            required
          />
          <span>
            I agree to the <span className="font-medium text-foreground">Privacy Policy</span>.
          </span>
        </label>

        <label className="flex items-start gap-3 text-sm text-muted-foreground">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-border"
            checked={marketingEmail}
            onChange={(e) => setMarketingEmail(e.target.checked)}
          />
          <span>Send me occasional product updates and marketing by email.</span>
        </label>

        <label className="flex items-start gap-3 text-sm text-muted-foreground">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-border"
            checked={marketingSms}
            onChange={(e) => setMarketingSms(e.target.checked)}
          />
          <span>Send me occasional product updates and marketing by SMS.</span>
        </label>
      </div>

      <GoogleAuthButton
        label={googleLoading ? "Opening Google…" : `Continue with Google as ${role}`}
        onClick={handleGoogleRegistration}
        disabled={loading || googleLoading}
      />

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t border-border/70" />
        </div>
        <div className="relative flex justify-center text-xs uppercase tracking-[0.2em] text-muted-foreground">
          <span className="bg-background px-2">Or</span>
        </div>
      </div>

      <Button type="submit" className="w-full" disabled={loading || googleLoading}>
        {loading ? "Creating account…" : `Create ${role} account`}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="underline underline-offset-4 hover:text-foreground">
          Sign in
        </Link>
      </p>
    </form>
  );
}
