import type { Metadata } from "next";

export const metadata: Metadata = { title: "Parent Dashboard" };

export default function ParentDashboardPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">Parent Dashboard</h1>
      {/* TODO: learners list, upcoming bookings, find a teacher CTA */}
    </div>
  );
}
