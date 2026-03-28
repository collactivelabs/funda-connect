import { Suspense } from "react";
import type { Metadata } from "next";
import { VerifyEmailForm } from "@/components/auth/verify-email-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Verify Email" };

export default function VerifyEmailPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Verify your email</CardTitle>
          <CardDescription>We&apos;re confirming your account now.</CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense>
            <VerifyEmailForm />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}
