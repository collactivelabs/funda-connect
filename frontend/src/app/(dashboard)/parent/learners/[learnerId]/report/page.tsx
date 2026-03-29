import { Suspense } from "react";
import type { Metadata } from "next";
import { LearnerReportPage } from "@/components/parent/learner-report-page";

export const metadata: Metadata = { title: "Learner Progress Report" };

export default async function ParentLearnerReportRoute({
  params,
}: {
  params: Promise<{ learnerId: string }>;
}) {
  const { learnerId } = await params;

  return (
    <Suspense>
      <LearnerReportPage learnerId={learnerId} />
    </Suspense>
  );
}
