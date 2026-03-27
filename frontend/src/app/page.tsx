"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/stores/auth.store";

export default function HomePage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  // Redirect logged-in users straight to their dashboard
  useEffect(() => {
    if (!user) return;
    const dest =
      user.role === "admin" ? "/admin" : user.role === "teacher" ? "/teacher" : "/parent";
    router.replace(dest);
  }, [user, router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
      <div className="space-y-4">
        <Badge variant="secondary" className="text-xs">
          Beta — South Africa Only
        </Badge>
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          Funda<span className="text-primary">Connect</span>
        </h1>
        <p className="mx-auto max-w-xl text-muted-foreground">
          Connecting qualified South African teachers with homeschooling
          families. CAPS, Cambridge &amp; IEB aligned.
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-4">
        <Link href="/teachers" className={buttonVariants({ size: "lg" })}>
          Browse Teachers
        </Link>
        <Link href="/register?role=parent" className={buttonVariants({ variant: "outline", size: "lg" })}>
          Sign up as Parent
        </Link>
        <Link href="/register?role=teacher" className={buttonVariants({ variant: "ghost", size: "lg" })}>
          Teach on FundaConnect
        </Link>
      </div>

      <p className="text-xs text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="underline underline-offset-4 hover:text-foreground">
          Sign in
        </Link>
      </p>
    </main>
  );
}
