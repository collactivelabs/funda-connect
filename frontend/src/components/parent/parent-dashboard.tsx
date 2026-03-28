"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { AddLearnerDialog } from "./add-learner-dialog";
import { PaymentHistorySection } from "./payment-history-section";
import { PaymentStatusBanner } from "./payment-status-banner";
import { BookingList } from "@/components/shared/booking-list";
import type { Learner } from "@/types";

export function ParentDashboard() {
  const [learners, setLearners] = useState<Learner[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);

  useEffect(() => {
    apiClient.parents.getLearners()
      .then(({ data }) => setLearners(data as Learner[]))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  function handleLearnerAdded(learner: Learner) {
    setLearners((prev) => [...prev, learner]);
  }

  return (
    <div className="space-y-8">
      <PaymentStatusBanner />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Manage your learners and bookings.</p>
        </div>
        <Link href="/teachers" className={buttonVariants()}>
          Find a Teacher
        </Link>
      </div>

      {/* Learners section */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Learners</h2>
          <Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
            + Add Learner
          </Button>
        </div>

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2].map((i) => (
              <Card key={i}>
                <CardHeader>
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-20" />
                </CardHeader>
              </Card>
            ))}
          </div>
        ) : learners.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <p className="mb-4 text-muted-foreground">
                No learners added yet. Add your child to start booking lessons.
              </p>
              <Button variant="outline" onClick={() => setAddOpen(true)}>
                + Add your first learner
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {learners.map((learner) => (
              <Card key={learner.id}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">
                    {learner.firstName} {learner.lastName}
                  </CardTitle>
                  <CardDescription>{learner.grade}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Badge variant="secondary">{learner.curriculum}</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <Separator />

      <PaymentHistorySection />

      <Separator />

      {/* Bookings section */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">Lessons</h2>
        <BookingList role="parent" />
      </section>

      {/* Add learner dialog */}
      <AddLearnerDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onAdded={handleLearnerAdded}
      />
    </div>
  );
}
