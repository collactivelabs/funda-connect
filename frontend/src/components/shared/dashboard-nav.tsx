"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { NotificationCenter } from "@/components/shared/notification-center";
import { Badge } from "@/components/ui/badge";
import { buttonVariants, Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth.store";

export function DashboardNav() {
  const router = useRouter();
  const { user, token, logout } = useAuthStore();

  async function handleLogout() {
    await logout();
    router.push("/");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="font-semibold tracking-tight">
          Funda<span className="text-primary">Connect</span>
        </Link>

        <nav className="hidden sm:flex items-center gap-1 mr-4">
          <Link
            href="/teachers"
            className="text-sm text-muted-foreground hover:text-foreground px-3 py-1 rounded-md transition-colors"
          >
            Find Teachers
          </Link>
          {user?.role === "parent" && (
            <Link
              href="/parent"
              className="text-sm text-muted-foreground hover:text-foreground px-3 py-1 rounded-md transition-colors"
            >
              Dashboard
            </Link>
          )}
          {user?.role === "teacher" && (
            <Link
              href="/teacher"
              className="text-sm text-muted-foreground hover:text-foreground px-3 py-1 rounded-md transition-colors"
            >
              Dashboard
            </Link>
          )}
          {user?.role === "admin" && (
            <Link
              href="/admin"
              className="text-sm text-muted-foreground hover:text-foreground px-3 py-1 rounded-md transition-colors"
            >
              Admin
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-3">
          {user && (
            <>
              <NotificationCenter />
              <span className="hidden text-sm text-muted-foreground sm:block">
                {user.firstName} {user.lastName}
              </span>
              <Badge variant="secondary" className="capitalize">
                {user.role}
              </Badge>
            </>
          )}
          {user && token ? (
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              Sign out
            </Button>
          ) : (
            <Link href="/login" className={buttonVariants({ variant: "ghost", size: "sm" })}>
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
