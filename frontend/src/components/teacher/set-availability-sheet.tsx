"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import type { ApiError, AvailabilitySlot } from "@/types";
import type { AxiosError } from "axios";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// 30-min intervals from 06:00 to 22:00
const TIME_OPTIONS: string[] = [];
for (let h = 6; h <= 22; h++) {
  TIME_OPTIONS.push(`${String(h).padStart(2, "0")}:00`);
  if (h < 22) TIME_OPTIONS.push(`${String(h).padStart(2, "0")}:30`);
}

function formatTime(t: string) {
  const [h, m] = t.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return `${hour}:${m.toString().padStart(2, "0")} ${period}`;
}

interface LocalSlot {
  id: string; // temp client-side ID
  startTime: string;
  endTime: string;
}

interface SetAvailabilitySheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (slots: AvailabilitySlot[]) => void;
}

let nextId = 1;
function tempId() { return `tmp-${nextId++}`; }

export function SetAvailabilitySheet({ open, onOpenChange, onSaved }: SetAvailabilitySheetProps) {
  // daySlots: map from dayOfWeek (0-6) to list of LocalSlot
  const [daySlots, setDaySlots] = useState<Record<number, LocalSlot[]>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load existing slots when sheet opens
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    apiClient.teachers.getAvailability()
      .then(({ data }) => {
        const slots = data as AvailabilitySlot[];
        const map: Record<number, LocalSlot[]> = {};
        for (const s of slots) {
          (map[s.dayOfWeek] ??= []).push({ id: tempId(), startTime: s.startTime, endTime: s.endTime });
        }
        setDaySlots(map);
      })
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [open]);

  function addSlot(day: number) {
    setDaySlots((prev) => {
      const existing = prev[day] ?? [];
      // Default: start after last slot or 08:00
      const lastEnd = existing[existing.length - 1]?.endTime;
      const startTime = lastEnd ?? "08:00";
      // End time = start + 1 hour
      const [h, m] = startTime.split(":").map(Number);
      const endHour = Math.min(h + 1, 22);
      const endTime = `${String(endHour).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
      return { ...prev, [day]: [...existing, { id: tempId(), startTime, endTime }] };
    });
  }

  function removeSlot(day: number, id: string) {
    setDaySlots((prev) => ({
      ...prev,
      [day]: (prev[day] ?? []).filter((s) => s.id !== id),
    }));
  }

  function updateSlot(day: number, id: string, field: "startTime" | "endTime", value: string) {
    setDaySlots((prev) => ({
      ...prev,
      [day]: (prev[day] ?? []).map((s) => s.id === id ? { ...s, [field]: value } : s),
    }));
  }

  async function handleSave() {
    setError(null);
    setSaving(true);
    try {
      // Flatten to API format — skip invalid slots (start >= end)
      const slots = Object.entries(daySlots).flatMap(([day, daySlotList]) =>
        daySlotList
          .filter((s) => s.startTime < s.endTime)
          .map((s) => ({
            day_of_week: Number(day),
            start_time: s.startTime,
            end_time: s.endTime,
          }))
      );
      const { data } = await apiClient.teachers.setAvailability({ slots });
      onSaved(data as AvailabilitySlot[]);
      onOpenChange(false);
    } catch (err) {
      const axiosErr = err as AxiosError<ApiError>;
      setError(axiosErr.response?.data?.detail ?? "Failed to save availability.");
    } finally {
      setSaving(false);
    }
  }

  const totalSlots = Object.values(daySlots).reduce((sum, s) => sum + s.length, 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto p-6" style={{ maxWidth: "40rem" }}>
        <SheetHeader className="mb-6">
          <SheetTitle>Set Weekly Availability</SheetTitle>
          <SheetDescription>
            Add time slots for each day you're available. These are shown to parents when booking.
          </SheetDescription>
        </SheetHeader>

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading current availability…</p>
        ) : (
          <div className="space-y-6">
            {DAY_NAMES.map((dayName, day) => {
              const slots = daySlots[day] ?? [];
              return (
                <div key={day}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{dayName}</span>
                      {slots.length > 0 && (
                        <Badge variant="secondary" className="text-xs">{slots.length} slot{slots.length !== 1 ? "s" : ""}</Badge>
                      )}
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => addSlot(day)}
                      className="text-xs"
                    >
                      + Add slot
                    </Button>
                  </div>

                  {slots.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No slots — unavailable this day.</p>
                  ) : (
                    <div className="space-y-2">
                      {slots.map((slot) => (
                        <div key={slot.id} className="flex items-center gap-3 pl-1">
                          <Select
                            value={slot.startTime}
                            onValueChange={(v) => updateSlot(day, slot.id, "startTime", v ?? slot.startTime)}
                          >
                            <SelectTrigger className="h-9 text-sm min-w-[8rem] flex-1">
                              <SelectValue>{formatTime(slot.startTime)}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              {TIME_OPTIONS.map((t) => (
                                <SelectItem key={t} value={t} className="text-sm">{formatTime(t)}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <span className="text-muted-foreground text-sm">to</span>
                          <Select
                            value={slot.endTime}
                            onValueChange={(v) => updateSlot(day, slot.id, "endTime", v ?? slot.endTime)}
                          >
                            <SelectTrigger className="h-9 text-sm min-w-[8rem] flex-1">
                              <SelectValue>{formatTime(slot.endTime)}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              {TIME_OPTIONS.filter((t) => t > slot.startTime).map((t) => (
                                <SelectItem key={t} value={t} className="text-sm">{formatTime(t)}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                            onClick={() => removeSlot(day, slot.id)}
                          >
                            ×
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                  {day < 6 && <Separator className="mt-4" />}
                </div>
              );
            })}
          </div>
        )}

        {error && (
          <Alert variant="destructive" className="mt-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex gap-3 mt-8">
          <Button variant="outline" className="flex-1" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button className="flex-1" onClick={handleSave} disabled={saving || loading}>
            {saving ? "Saving…" : `Save ${totalSlots > 0 ? `(${totalSlots} slot${totalSlots !== 1 ? "s" : ""})` : "availability"}`}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
