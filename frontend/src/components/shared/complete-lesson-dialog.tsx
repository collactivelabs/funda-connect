"use client";

import { useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Booking, TopicReference } from "@/types";

function getErrorMessage(error: unknown, fallback: string) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;
}

function formatLessonDate(iso: string) {
  return new Date(iso).toLocaleString("en-ZA", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function CompleteLessonDialog({
  booking,
  onCompleted,
}: {
  booking: Booking;
  onCompleted: (booking: Booking) => void;
}) {
  const [open, setOpen] = useState(false);
  const [lessonNotes, setLessonNotes] = useState("");
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [topics, setTopics] = useState<TopicReference[]>([]);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const topicContext = useMemo(
    () => ({
      subject: booking.subject?.slug,
      grade: booking.learner?.grade,
      curriculum: booking.learner?.curriculum,
    }),
    [booking.learner?.curriculum, booking.learner?.grade, booking.subject?.slug],
  );

  useEffect(() => {
    if (!open) {
      setLessonNotes(booking.lessonNotes ?? "");
      setSelectedTopics(booking.topicsCovered ?? []);
      setTopics([]);
      setLoadingTopics(false);
      setError(null);
      return;
    }

    setLessonNotes(booking.lessonNotes ?? "");
    setSelectedTopics(booking.topicsCovered ?? []);

    if (!topicContext.subject || !topicContext.grade || !topicContext.curriculum) {
      setTopics([]);
      return;
    }

    let cancelled = false;

    async function loadTopics() {
      setLoadingTopics(true);
      try {
        const { data } = await apiClient.referenceData.listTopics(topicContext);
        if (!cancelled) {
          setTopics(data);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(getErrorMessage(err, "Could not load lesson topics right now."));
        }
      } finally {
        if (!cancelled) {
          setLoadingTopics(false);
        }
      }
    }

    void loadTopics();

    return () => {
      cancelled = true;
    };
  }, [booking.lessonNotes, booking.topicsCovered, open, topicContext]);

  function toggleTopic(topicId: string) {
    setSelectedTopics((prev) =>
      prev.includes(topicId)
        ? prev.filter((item) => item !== topicId)
        : [...prev, topicId].slice(0, 20),
    );
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);

    try {
      const { data } = await apiClient.bookings.complete(booking.id, {
        lessonNotes: lessonNotes.trim() || null,
        topicsCovered: selectedTopics,
      });
      onCompleted(data as Booking);
      setOpen(false);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not mark this lesson complete."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-7 text-xs"
        onClick={() => setOpen(true)}
      >
        Mark complete
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Complete lesson</DialogTitle>
            <DialogDescription>
              Capture what was covered so the parent can track learner progress.
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
            <div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
              {booking.subject?.name ?? "Lesson"} · {formatLessonDate(booking.scheduledAt)}
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor={`lesson-notes-${booking.id}`}>
                Lesson notes
              </label>
              <Textarea
                id={`lesson-notes-${booking.id}`}
                value={lessonNotes}
                onChange={(event) => setLessonNotes(event.target.value)}
                placeholder="Summarise what you covered, what went well, and anything the parent should know."
                className="min-h-28"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">Topics covered</p>
                  <p className="text-xs text-muted-foreground">
                    Select the main concepts covered in this lesson.
                  </p>
                </div>
                {selectedTopics.length > 0 && (
                  <Badge variant="secondary">{selectedTopics.length} selected</Badge>
                )}
              </div>

              {loadingTopics ? (
                <p className="text-sm text-muted-foreground">Loading available topics...</p>
              ) : topics.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border/60 p-3 text-sm text-muted-foreground">
                  No topic suggestions are available for this learner and subject yet. You can still complete the lesson with notes only.
                </div>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  {topics.map((topic) => {
                    const selected = selectedTopics.includes(topic.id);
                    return (
                      <button
                        key={topic.id}
                        type="button"
                        onClick={() => toggleTopic(topic.id)}
                        className={cn(
                          "rounded-lg border p-3 text-left text-sm transition-colors",
                          selected
                            ? "border-primary bg-primary/10 text-foreground"
                            : "border-border/60 bg-background hover:border-primary/40 hover:bg-muted/30",
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-medium leading-snug">{topic.name}</span>
                          {topic.term ? (
                            <Badge variant="outline" className="shrink-0">
                              Term {topic.term}
                            </Badge>
                          ) : null}
                        </div>
                        {topic.referenceCode ? (
                          <p className="mt-1 text-xs text-muted-foreground">{topic.referenceCode}</p>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <DialogFooter showCloseButton>
            <Button type="button" disabled={submitting} onClick={() => void handleSubmit()}>
              {submitting ? "Saving..." : "Confirm completion"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
