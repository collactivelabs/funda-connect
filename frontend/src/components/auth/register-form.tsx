"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";
import type { AuthResponse } from "@/types";

export function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { setUser, setAccessToken } = useAuthStore();

  const initialRole: "parent" | "teacher" = params.get("role") === "teacher" ? "teacher" : "parent";
  const [role, setRole] = useState<"parent" | "teacher">(initialRole);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      }) as { data: AuthResponse };
      setAccessToken(data.access_token);
      setUser(data.user);
      router.push(data.user.role === "teacher" ? "/teacher" : "/parent");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Registration failed. Please try again.");
    } finally {
      setLoading(false);
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

      <Button type="submit" className="w-full" disabled={loading}>
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
