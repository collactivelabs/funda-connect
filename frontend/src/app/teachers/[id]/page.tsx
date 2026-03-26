"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { BookingDialog } from "@/components/booking/booking-dialog";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";
import type { AvailabilitySlot, Review, TeacherProfile } from "@/types";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function formatTime(t: string) {
  const [h, m] = t.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return `${hour}:${m.toString().padStart(2, "0")} ${period}`;
}

function groupByDay(slots: AvailabilitySlot[]) {
  const map: Record<number, AvailabilitySlot[]> = {};
  for (const slot of slots) {
    (map[slot.dayOfWeek] ??= []).push(slot);
  }
  return map;
}

function ProfileSkeleton() {
  return (
    <div className="space-y-8">
      <div className="flex items-start gap-6">
        <Skeleton className="h-20 w-20 rounded-full shrink-0" />
        <div className="space-y-3 flex-1">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-72" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

export default function TeacherProfilePage() {
  const { id } = useParams<{ id: string }>();
  const user = useAuthStore((s) => s.user);

  const [teacher, setTeacher] = useState<TeacherProfile | null>(null);
  const [availability, setAvailability] = useState<AvailabilitySlot[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [bookingOpen, setBookingOpen] = useState(false);

  useEffect(() => {
    Promise.all([
      apiClient.teachers.get(id),
      apiClient.teachers.getPublicAvailability(id),
      apiClient.reviews.listForTeacher(id),
    ])
      .then(([profileRes, availRes, reviewsRes]) => {
        setTeacher(profileRes.data as TeacherProfile);
        setAvailability(availRes.data as AvailabilitySlot[]);
        setReviews(reviewsRes.data as Review[]);
      })
      .catch((err) => {
        if (err.response?.status === 404) setNotFound(true);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto max-w-4xl px-4 py-12">
          <ProfileSkeleton />
        </div>
      </div>
    );
  }

  if (notFound || !teacher) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Alert className="max-w-sm">
          <AlertDescription>
            Teacher not found.{" "}
            <Link href="/teachers" className="underline">Browse all teachers</Link>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const name = `${teacher.user.firstName} ${teacher.user.lastName}`;
  const rate = teacher.hourlyRateCents
    ? `R${(teacher.hourlyRateCents / 100).toFixed(0)}/hr`
    : "Rate on request";

  const dayMap = groupByDay(availability);
  const activeDays = Object.keys(dayMap).map(Number).sort();

  const canBook = user?.role === "parent";

  return (
    <div className="min-h-screen bg-background">
      {/* Nav breadcrumb */}
      <div className="border-b">
        <div className="container mx-auto max-w-4xl px-4 py-4 text-sm text-muted-foreground">
          <Link href="/teachers" className="hover:text-foreground transition-colors">
            ← All teachers
          </Link>
        </div>
      </div>

      <div className="container mx-auto max-w-4xl px-4 py-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start gap-6">
          {/* Avatar placeholder */}
          <div className="h-20 w-20 rounded-full bg-muted flex items-center justify-center shrink-0">
            <span className="text-2xl font-semibold text-muted-foreground">
              {teacher.user.firstName[0]}{teacher.user.lastName[0]}
            </span>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h1 className="text-2xl font-bold">{name}</h1>
              {teacher.isPremium && <Badge variant="default">Premium</Badge>}
            </div>
            {teacher.headline && (
              <p className="text-muted-foreground mb-2">{teacher.headline}</p>
            )}
            <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
              {teacher.averageRating ? (
                <span>{teacher.averageRating.toFixed(1)} ★ ({teacher.totalReviews} reviews)</span>
              ) : (
                <span>No reviews yet</span>
              )}
              <span>{teacher.totalLessons} lessons taught</span>
              {teacher.yearsExperience && (
                <span>{teacher.yearsExperience} yrs experience</span>
              )}
              {teacher.province && <span>{teacher.province}</span>}
            </div>
          </div>

          {/* Booking CTA */}
          <div className="sm:text-right shrink-0">
            <div className="text-2xl font-bold mb-2">{rate}</div>
            {canBook ? (
              <Button size="lg" onClick={() => setBookingOpen(true)}>
                Book a Lesson
              </Button>
            ) : user?.role === "teacher" ? (
              <p className="text-sm text-muted-foreground">Teachers cannot book lessons.</p>
            ) : (
              <Link
                href={`/login?redirect=/teachers/${id}`}
                className={buttonVariants({ size: "lg" })}
              >
                Log in to Book
              </Link>
            )}
          </div>
        </div>

        <Separator />

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left column: bio + subjects */}
          <div className="lg:col-span-2 space-y-6">
            {/* Bio */}
            {teacher.bio && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">About</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed whitespace-pre-line">{teacher.bio}</p>
                </CardContent>
              </Card>
            )}

            {/* Subjects */}
            {teacher.subjects.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Subjects</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {teacher.subjects.map((s) => (
                      <div key={s.id} className="flex items-start justify-between gap-4">
                        <div>
                          <span className="font-medium text-sm">{s.subjectName}</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {s.gradeLevels.map((g) => (
                              <Badge key={g} variant="outline" className="text-xs">{g}</Badge>
                            ))}
                          </div>
                        </div>
                        <Badge variant="secondary" className="shrink-0">{s.curriculum}</Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Reviews */}
            {reviews.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Reviews ({reviews.length})</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {reviews.map((r) => (
                    <div key={r.id}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium">
                          {"★".repeat(r.rating)}{"☆".repeat(5 - r.rating)}
                        </span>
                      </div>
                      {r.comment && (
                        <p className="text-sm text-muted-foreground">{r.comment}</p>
                      )}
                      {r.teacherReply && (
                        <div className="mt-2 pl-3 border-l-2 border-muted">
                          <p className="text-xs text-muted-foreground italic">{r.teacherReply}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right column: curricula + availability */}
          <div className="space-y-6">
            {/* Curricula */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Curricula</CardTitle>
              </CardHeader>
              <CardContent>
                {teacher.curricula.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {teacher.curricula.map((c) => (
                      <Badge key={c} variant="secondary">{c}</Badge>
                    ))}
                  </div>
                ) : (
                  <CardDescription>Not specified</CardDescription>
                )}
              </CardContent>
            </Card>

            {/* Availability */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Weekly Availability</CardTitle>
              </CardHeader>
              <CardContent>
                {activeDays.length === 0 ? (
                  <CardDescription>No availability set yet.</CardDescription>
                ) : (
                  <div className="space-y-2 text-sm">
                    {activeDays.map((day) => (
                      <div key={day} className="flex items-start gap-3">
                        <span className="font-medium w-9 shrink-0">{DAY_NAMES[day].slice(0, 3)}</span>
                        <div className="flex flex-wrap gap-1">
                          {dayMap[day].map((slot) => (
                            <Badge key={slot.id} variant="outline" className="text-xs font-normal">
                              {formatTime(slot.startTime)} – {formatTime(slot.endTime)}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Booking dialog */}
      {teacher && (
        <BookingDialog
          teacher={teacher}
          open={bookingOpen}
          onOpenChange={setBookingOpen}
        />
      )}
    </div>
  );
}
