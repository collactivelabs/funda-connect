import type { Metadata } from "next";
import { TeacherSearch } from "@/components/teacher/teacher-search";

export const metadata: Metadata = {
  title: "Find a Teacher — FundaConnect",
  description: "Browse verified homeschool tutors in South Africa. Filter by subject, curriculum, grade, and location.",
};

export default function TeachersPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="border-b">
        <div className="container mx-auto px-4 py-8">
          <h1 className="text-3xl font-bold tracking-tight">Find a Teacher</h1>
          <p className="text-muted-foreground mt-1">
            Browse verified tutors specialising in CAPS, Cambridge, and IEB curricula.
          </p>
        </div>
      </div>
      <div className="container mx-auto px-4 py-8">
        <TeacherSearch />
      </div>
    </div>
  );
}
