import { Suspense } from "react";
import type { Metadata } from "next";
import { GoogleOAuthComplete } from "@/components/auth/google-oauth-complete";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Complete Sign In" };

export default function OAuthCompletePage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Completing sign-in</CardTitle>
          <CardDescription>We&apos;re connecting your Google account now.</CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense>
            <GoogleOAuthComplete />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}
