"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { EditProfileDialog } from "./edit-profile-dialog";
import { SetAvailabilitySheet } from "./set-availability-sheet";
import { ManageSubjectsDialog } from "./manage-subjects-dialog";
import { UploadDocumentDialog } from "./upload-document-dialog";
import { BookingList } from "@/components/shared/booking-list";
import type { AvailabilitySlot, TeacherProfile, TeacherSubject } from "@/types";

const VERIFICATION_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending: { label: "Pending verification", variant: "secondary" },
  under_review: { label: "Under review", variant: "outline" },
  verified: { label: "Verified", variant: "default" },
  rejected: { label: "Rejected", variant: "destructive" },
  suspended: { label: "Suspended", variant: "destructive" },
};

export function TeacherDashboard() {
  const [profile, setProfile] = useState<TeacherProfile | null>(null);
  const [availability, setAvailability] = useState<AvailabilitySlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [availOpen, setAvailOpen] = useState(false);
  const [subjectsOpen, setSubjectsOpen] = useState(false);

  useEffect(() => {
    Promise.all([
      apiClient.teachers.getMe(),
      apiClient.teachers.getAvailability(),
    ])
      .then(([profileRes, availRes]) => {
        setProfile(profileRes.data as TeacherProfile);
        setAvailability(availRes.data as AvailabilitySlot[]);
      })
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 sm:grid-cols-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
        </div>
      </div>
    );
  }

  const statusInfo = VERIFICATION_LABELS[profile?.verificationStatus ?? "pending"];

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {profile?.user.firstName} {profile?.user.lastName}
          </h1>
          <p className="text-muted-foreground">
            {profile?.headline ?? "Complete your profile to start receiving bookings."}
          </p>
        </div>
        <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
      </div>

      {/* Verification prompt */}
      {profile?.verificationStatus === "pending" && (
        <Alert>
          <AlertDescription className="flex items-center justify-between gap-4 flex-wrap">
            <span>
              Your account is pending verification. Upload your SACE certificate and qualification documents to get verified and start listing lessons.
            </span>
            <UploadDocumentDialog />
          </AlertDescription>
        </Alert>
      )}

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Lessons</CardDescription>
            <CardTitle className="text-3xl">{profile?.totalLessons ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Average Rating</CardDescription>
            <CardTitle className="text-3xl">
              {profile?.averageRating ? `${profile.averageRating.toFixed(1)} ★` : "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Hourly Rate</CardDescription>
            <CardTitle className="text-3xl">
              {profile?.hourlyRateCents
                ? `R${(profile.hourlyRateCents / 100).toFixed(0)}`
                : "Not set"}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Profile setup */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Profile</h2>
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            Edit Profile
          </Button>
        </div>
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Subjects added</span>
              <div className="flex items-center gap-2">
                <span className="font-medium">{profile?.subjects.length ?? 0}</span>
                <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={() => setSubjectsOpen(true)}>
                  Manage
                </Button>
              </div>
            </div>
            <Separator />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Curricula</span>
              <div className="flex gap-1 flex-wrap justify-end">
                {profile?.curricula.length
                  ? profile.curricula.map((c) => <Badge key={c} variant="secondary">{c}</Badge>)
                  : <span className="text-muted-foreground">None</span>
                }
              </div>
            </div>
            <Separator />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Province</span>
              <span className="font-medium">{profile?.province ?? "Not set"}</span>
            </div>
            <Separator />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Availability slots</span>
              <span className="font-medium">{availability.length}</span>
            </div>
            <Separator />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Listed on marketplace</span>
              <Badge variant={profile?.isListed ? "default" : "secondary"}>
                {profile?.isListed ? "Listed" : "Unlisted"}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </section>

      <Separator />

      {/* Upcoming bookings */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">Lessons</h2>
        <BookingList role="teacher" />
      </section>

      {/* Quick actions */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">Quick Actions</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Card
            className="cursor-pointer transition-colors hover:bg-muted/50"
            onClick={() => setEditOpen(true)}
          >
            <CardHeader>
              <CardTitle className="text-base">Edit Profile</CardTitle>
              <CardDescription>
                Update your bio, hourly rate, and curricula to attract more bookings.
              </CardDescription>
            </CardHeader>
          </Card>
          <Card
            className="cursor-pointer transition-colors hover:bg-muted/50"
            onClick={() => setAvailOpen(true)}
          >
            <CardHeader>
              <CardTitle className="text-base">Set Availability</CardTitle>
              <CardDescription>Configure your weekly schedule for bookings.</CardDescription>
            </CardHeader>
          </Card>
          <Card
            className="cursor-pointer transition-colors hover:bg-muted/50"
            onClick={() => setSubjectsOpen(true)}
          >
            <CardHeader>
              <CardTitle className="text-base">Manage Subjects</CardTitle>
              <CardDescription>Add subjects, grade levels, and curricula you teach.</CardDescription>
            </CardHeader>
          </Card>
        </div>
      </section>

      {/* Modals */}
      {profile && (
        <EditProfileDialog
          profile={profile}
          open={editOpen}
          onOpenChange={setEditOpen}
          onSaved={(updated) => setProfile(updated)}
        />
      )}
      <SetAvailabilitySheet
        open={availOpen}
        onOpenChange={setAvailOpen}
        onSaved={(slots) => setAvailability(slots)}
      />
      {profile && (
        <ManageSubjectsDialog
          teacherSubjects={profile.subjects}
          open={subjectsOpen}
          onOpenChange={setSubjectsOpen}
          onChanged={(subjects) => setProfile((prev) => prev ? { ...prev, subjects } : prev)}
        />
      )}
    </div>
  );
}
