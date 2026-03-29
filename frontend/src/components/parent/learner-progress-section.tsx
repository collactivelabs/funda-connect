"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";
import type { Learner, LearnerProgress } from "@/types";

function formatDateTime(iso?: string | null) {
  if (!iso) return "Not yet";
  return new Date(iso).toLocaleString("en-ZA", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatHours(totalMinutes: number) {
  const hours = totalMinutes / 60;
  return `${hours.toLocaleString("en-ZA", { maximumFractionDigits: hours % 1 === 0 ? 0 : 1 })} hrs`;
}

function ProgressSkeleton() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {[1, 2].map((item) => (
        <Card key={item}>
          <CardHeader>
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-32" />
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function LearnerProgressCard({ progress }: { progress: LearnerProgress }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">{progress.learnerName}</CardTitle>
            <CardDescription>
              {progress.grade} · {progress.curriculum}
            </CardDescription>
          </div>
          <Badge variant="secondary">{progress.subjectCount} subjects</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
            <p className="text-xs text-muted-foreground">Completed</p>
            <p className="mt-1 text-xl font-semibold">{progress.completedLessons}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
            <p className="text-xs text-muted-foreground">Upcoming</p>
            <p className="mt-1 text-xl font-semibold">{progress.upcomingLessons}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
            <p className="text-xs text-muted-foreground">Learning time</p>
            <p className="mt-1 text-xl font-semibold">{formatHours(progress.totalMinutes)}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
            <p className="text-xs text-muted-foreground">Topics covered</p>
            <p className="mt-1 text-xl font-semibold">{progress.topicCount}</p>
          </div>
        </div>

        <div className="space-y-2">
          <h3 className="text-sm font-medium">Subject progress</h3>
          {progress.subjects.length === 0 ? (
            <p className="text-sm text-muted-foreground">No completed lessons yet for this learner.</p>
          ) : (
            <div className="space-y-2">
              {progress.subjects.map((subject) => (
                <div
                  key={subject.subjectId}
                  className="flex flex-col gap-1 rounded-lg border border-border/60 p-3 text-sm sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="font-medium">{subject.subjectName}</p>
                    <p className="text-muted-foreground">
                      {subject.completedLessons} lessons · {formatHours(subject.totalMinutes)}
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Last lesson {formatDateTime(subject.latestLessonAt)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {progress.topicsCovered.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Recent topics</h3>
            <div className="flex flex-wrap gap-2">
              {progress.topicsCovered.slice(0, 8).map((topic) => (
                <Badge key={topic.id} variant="outline">
                  {topic.name}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-medium">Recent completed lessons</h3>
            <p className="text-xs text-muted-foreground">
              Last update {formatDateTime(progress.lastCompletedAt)}
            </p>
          </div>
          {progress.recentLessons.length === 0 ? (
            <p className="text-sm text-muted-foreground">Completed lessons will appear here once teachers mark them off.</p>
          ) : (
            <div className="space-y-3">
              {progress.recentLessons.map((lesson) => (
                <div key={lesson.bookingId} className="rounded-lg border border-border/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{lesson.subjectName}</p>
                    <p className="text-xs text-muted-foreground">{formatDateTime(lesson.scheduledAt)}</p>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {lesson.teacherName} · {lesson.durationMinutes} min
                  </p>
                  {lesson.lessonNotes ? (
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                      {lesson.lessonNotes}
                    </p>
                  ) : null}
                  {lesson.topicsCovered.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {lesson.topicsCovered.map((topic) => (
                        <Badge key={topic.id} variant="secondary">
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
      </CardContent>
    </Card>
  );
}

export function LearnerProgressSection({ learners }: { learners: Learner[] }) {
  const [progress, setProgress] = useState<LearnerProgress[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (learners.length === 0) {
      setProgress([]);
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function loadProgress() {
      setLoading(true);
      try {
        const results = await Promise.allSettled(
          learners.map((learner) => apiClient.parents.getLearnerProgress(learner.id)),
        );
        if (cancelled) {
          return;
        }
        const fulfilled = results
          .filter((result) => result.status === "fulfilled")
          .map((result) => (result as PromiseFulfilledResult<{ data: LearnerProgress }>).value.data);
        setProgress(fulfilled);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadProgress();

    return () => {
      cancelled = true;
    };
  }, [learners]);

  if (learners.length === 0) {
    return null;
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Learner Progress</h2>
        <p className="text-sm text-muted-foreground">
          Review completed lessons, covered topics, and overall learning time for each learner.
        </p>
      </div>

      {loading ? (
        <ProgressSkeleton />
      ) : progress.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-8 text-sm text-muted-foreground">
            Progress will appear here once teachers start completing lessons with notes.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {progress.map((item) => (
            <LearnerProgressCard key={item.learnerId} progress={item} />
          ))}
        </div>
      )}
    </section>
  );
}
