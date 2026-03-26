import { Suspense } from "react";
import type { Metadata } from "next";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RegisterForm } from "@/components/auth/register-form";

export const metadata: Metadata = { title: "Create Account" };

export default function RegisterPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Create account</CardTitle>
          <CardDescription>Join as a parent or a teacher.</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Suspense required because RegisterForm uses useSearchParams() */}
          <Suspense>
            <RegisterForm />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}
