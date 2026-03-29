import { AccountPrivacyCard } from "@/components/account/account-privacy-card";
import { SessionManagementCard } from "@/components/auth/session-management-card";
import { VerifyEmailBanner } from "@/components/auth/verify-email-banner";
import { DashboardNav } from "@/components/shared/dashboard-nav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <DashboardNav />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <VerifyEmailBanner />
        <SessionManagementCard />
        <AccountPrivacyCard />
        {children}
      </main>
    </div>
  );
}
