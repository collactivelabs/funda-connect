"use client";

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function HomePage() {
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

      <div className="flex gap-4">
        <Link href="/register?role=parent" className={buttonVariants({ size: "lg" })}>
          Find a Teacher
        </Link>
        <Link href="/register?role=teacher" className={buttonVariants({ variant: "outline", size: "lg" })}>
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
