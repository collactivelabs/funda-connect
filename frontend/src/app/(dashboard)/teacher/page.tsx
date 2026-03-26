import type { Metadata } from "next";
import { TeacherDashboard } from "@/components/teacher/teacher-dashboard";

export const metadata: Metadata = { title: "Teacher Dashboard" };

export default function TeacherDashboardPage() {
  return <TeacherDashboard />;
}
