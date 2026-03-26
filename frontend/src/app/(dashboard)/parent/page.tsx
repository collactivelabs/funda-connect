import { Suspense } from "react";
import type { Metadata } from "next";
import { ParentDashboard } from "@/components/parent/parent-dashboard";

export const metadata: Metadata = { title: "Parent Dashboard" };

export default function ParentDashboardPage() {
  return (
    <Suspense>
      <ParentDashboard />
    </Suspense>
  );
}
