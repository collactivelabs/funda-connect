"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { TeacherProfile } from "@/types";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface TeacherCardProps {
  teacher: TeacherProfile;
}

export function TeacherCard({ teacher }: TeacherCardProps) {
  const name = `${teacher.user.firstName} ${teacher.user.lastName}`;
  const rate = teacher.hourlyRateCents
    ? `R${(teacher.hourlyRateCents / 100).toFixed(0)}/hr`
    : "Rate on request";

  return (
    <Link href={`/teachers/${teacher.id}`} className="block group">
      <Card className="h-full transition-colors hover:bg-muted/50 group-focus-visible:ring-2 group-focus-visible:ring-ring">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-semibold truncate">{name}</h3>
                {teacher.isPremium && (
                  <Badge variant="default" className="text-xs shrink-0">Premium</Badge>
                )}
              </div>
              {teacher.headline && (
                <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">
                  {teacher.headline}
                </p>
              )}
            </div>
            <span className="text-sm font-semibold whitespace-nowrap">{rate}</span>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Stats row */}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            {teacher.averageRating ? (
              <span>{teacher.averageRating.toFixed(1)} ★ ({teacher.totalReviews})</span>
            ) : (
              <span>No reviews yet</span>
            )}
            <span>{teacher.totalLessons} lessons</span>
          </div>

          {/* Subjects */}
          {teacher.subjects.length > 0 && (
            <>
              <Separator />
              <div className="flex flex-wrap gap-1">
                {teacher.subjects.slice(0, 5).map((s) => (
                  <Badge key={s.id} variant="secondary" className="text-xs">
                    {s.subjectName}
                  </Badge>
                ))}
                {teacher.subjects.length > 5 && (
                  <Badge variant="outline" className="text-xs">
                    +{teacher.subjects.length - 5} more
                  </Badge>
                )}
              </div>
            </>
          )}

          {/* Curricula + province */}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{teacher.curricula.join(" · ") || "Curriculum TBC"}</span>
            {teacher.province && <span>{teacher.province}</span>}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
