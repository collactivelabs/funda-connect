import type { Metadata } from "next";

export const metadata: Metadata = { title: "Teacher Dashboard" };

export default function TeacherDashboardPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">Teacher Dashboard</h1>
      {/* TODO: bookings summary, earnings, upcoming lessons */}
    </div>
  );
}
