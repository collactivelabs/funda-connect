"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { buttonVariants, Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { LearnerReport } from "@/types";

function formatDate(value?: string | null) {
  if (!value) return "Not yet";
  return new Date(value).toLocaleString("en-ZA", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatHours(totalMinutes: number) {
  const hours = totalMinutes / 60;
  return `${hours.toLocaleString("en-ZA", { maximumFractionDigits: hours % 1 === 0 ? 0 : 1 })} hrs`;
}

function ReportSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-44" />
      <Skeleton className="h-[40rem] w-full" />
    </div>
  );
}

function DetailRow({
  label,
  value,
  emphasize = false,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border/60 py-3 last:border-0">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={cn("text-right text-sm", emphasize && "font-medium text-foreground")}>{value}</dd>
    </div>
  );
}

export function LearnerReportPage({ learnerId }: { learnerId: string }) {
  const [report, setReport] = useState<LearnerReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    apiClient.parents.getLearnerReport(learnerId)
      .then(({ data }) => {
        if (!cancelled) {
          setReport(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
          setError(detail ?? "Could not load this learner report.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [learnerId]);

  if (loading) {
    return <ReportSkeleton />;
  }

  if (!report) {
    return (
      <div className="space-y-4">
        <Link href="/parent" className={buttonVariants({ variant: "outline" })}>
          Back to dashboard
        </Link>
        <Card>
          <CardContent className="py-10 text-sm text-muted-foreground">
            {error ?? "Learner report not found."}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link href="/parent" className={buttonVariants({ variant: "outline" })}>
          Back to dashboard
        </Link>
        <Button type="button" onClick={() => window.print()}>
          Print or save as PDF
        </Button>
      </div>

      <Card className="mx-auto max-w-5xl">
        <CardHeader className="border-b border-border/60">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <CardTitle className="text-2xl">Learner Progress Report</CardTitle>
              <CardDescription>FundaConnect learner progress summary</CardDescription>
            </div>
            <div className="space-y-1 text-sm sm:text-right">
              <p className="font-medium">{report.reportReference}</p>
              <p className="text-muted-foreground">Generated {formatDate(report.generatedAt)}</p>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-8 py-6">
          <div className="grid gap-4 md:grid-cols-2">
            <Card size="sm" className="bg-muted/20">
              <CardHeader>
                <CardTitle>Learner</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>{report.learnerName}</p>
                <p className="text-muted-foreground">{report.grade}</p>
                <p className="text-muted-foreground">{report.curriculum}</p>
              </CardContent>
            </Card>

            <Card size="sm" className="bg-muted/20">
              <CardHeader>
                <CardTitle>Overview</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>{report.completedLessons} completed lessons</p>
                <p className="text-muted-foreground">{report.upcomingLessons} upcoming lessons</p>
                <p className="text-muted-foreground">Last completed lesson: {formatDate(report.lastCompletedAt)}</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="space-y-6">
              <div className="space-y-2">
                <h2 className="text-base font-semibold">Subject progress</h2>
                {report.subjects.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No completed lessons have been logged yet.</p>
                ) : (
                  <div className="space-y-2">
                    {report.subjects.map((subject) => (
                      <div key={subject.subjectId} className="rounded-lg border border-border/60 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-medium">{subject.subjectName}</p>
                          <Badge variant="secondary">{subject.completedLessons} lessons</Badge>
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {formatHours(subject.totalMinutes)} total learning time
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Latest lesson: {formatDate(subject.latestLessonAt)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <h2 className="text-base font-semibold">Recent completed lessons</h2>
                {report.recentLessons.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Lesson notes will appear here once teachers complete lessons.</p>
                ) : (
                  <div className="space-y-3">
                    {report.recentLessons.map((lesson) => (
                      <div key={lesson.bookingId} className="rounded-lg border border-border/60 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-medium">{lesson.subjectName}</p>
                          <p className="text-xs text-muted-foreground">{formatDate(lesson.scheduledAt)}</p>
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {lesson.teacherName} · {lesson.durationMinutes} minutes
                        </p>
                        {lesson.lessonNotes ? (
                          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                            {lesson.lessonNotes}
                          </p>
                        ) : null}
                        {lesson.topicsCovered.length > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {lesson.topicsCovered.map((topic) => (
                              <Badge key={topic.id} variant="outline">
                                {topic.name}
                              </Badge>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <h2 className="text-base font-semibold">Summary</h2>
              <Card size="sm" className="bg-muted/20">
                <CardContent className="pt-3">
                  <dl>
                    <DetailRow label="Completed lessons" value={String(report.completedLessons)} />
                    <DetailRow label="Upcoming lessons" value={String(report.upcomingLessons)} />
                    <DetailRow label="Subjects covered" value={String(report.subjectCount)} />
                    <DetailRow label="Topics covered" value={String(report.topicCount)} />
                    <DetailRow label="Learning time" value={formatHours(report.totalMinutes)} emphasize />
                  </dl>
                </CardContent>
              </Card>

              {report.topicsCovered.length > 0 && (
                <Card size="sm" className="bg-muted/20">
                  <CardHeader>
                    <CardTitle>Topic coverage</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-2">
                    {report.topicsCovered.map((topic) => (
                      <Badge key={topic.id} variant="secondary">
                        {topic.name}
                      </Badge>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
