"use client";

import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { apiClient } from "@/lib/api";
import type { ApiError, BlockedDate } from "@/types";
import type { AxiosError } from "axios";

interface LocalBlockedDate {
  id: string;
  date: string;
  reason: string;
}

interface ManageBlockedDatesSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (dates: BlockedDate[]) => void;
}

let nextTempId = 1;
function tempId() {
  return `blocked-${nextTempId++}`;
}

function nextIsoDate(daysAhead = 1) {
  const value = new Date();
  value.setDate(value.getDate() + daysAhead);
  return value.toISOString().slice(0, 10);
}

export function ManageBlockedDatesSheet({
  open,
  onOpenChange,
  onSaved,
}: ManageBlockedDatesSheetProps) {
  const [dates, setDates] = useState<LocalBlockedDate[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    setLoading(true);
    setError(null);

    apiClient.teachers.getBlockedDates()
      .then(({ data }) => {
        const blockedDates = (data as BlockedDate[]).map((item) => ({
          id: item.id,
          date: item.date,
          reason: item.reason ?? "",
        }));
        setDates(blockedDates);
      })
      .catch((err: unknown) => {
        const axiosErr = err as AxiosError<ApiError>;
        setError(axiosErr.response?.data?.detail ?? "Failed to load blocked dates.");
      })
      .finally(() => setLoading(false));
  }, [open]);

  function addDate() {
    setDates((prev) => [
      ...prev,
      {
        id: tempId(),
        date: nextIsoDate(prev.length + 1),
        reason: "",
      },
    ]);
  }

  function updateDate(id: string, field: "date" | "reason", value: string) {
    setDates((prev) => prev.map((item) => (
      item.id === id ? { ...item, [field]: value } : item
    )));
  }

  function removeDate(id: string) {
    setDates((prev) => prev.filter((item) => item.id !== id));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);

    try {
      const payload = {
        dates: dates
          .filter((item) => item.date)
          .map((item) => ({
            date: item.date,
            reason: item.reason.trim() || null,
          })),
      };
      const { data } = await apiClient.teachers.setBlockedDates(payload);
      onSaved(data as BlockedDate[]);
      onOpenChange(false);
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<ApiError>;
      setError(axiosErr.response?.data?.detail ?? "Failed to save blocked dates.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto p-6" style={{ maxWidth: "34rem" }}>
        <SheetHeader className="mb-6">
          <SheetTitle>Block specific dates</SheetTitle>
          <SheetDescription>
            Use this for holidays, travel, or days you do not want to appear as bookable, even if they fall within your weekly availability.
          </SheetDescription>
        </SheetHeader>

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading blocked dates…</p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Blocked dates</span>
                <Badge variant="secondary" className="text-xs">
                  {dates.length}
                </Badge>
              </div>
              <Button type="button" variant="outline" size="sm" className="text-xs" onClick={addDate}>
                + Add date
              </Button>
            </div>

            {dates.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border/60 p-4 text-sm text-muted-foreground">
                No blocked dates yet. Add a date when you know you will be unavailable.
              </div>
            ) : (
              <div className="space-y-3">
                {dates.map((item) => (
                  <div key={item.id} className="rounded-lg border border-border/60 p-3">
                    <div className="grid gap-3 sm:grid-cols-[10rem_1fr_auto] sm:items-end">
                      <div className="space-y-1.5">
                        <Label htmlFor={`blocked-date-${item.id}`}>Date</Label>
                        <Input
                          id={`blocked-date-${item.id}`}
                          type="date"
                          value={item.date}
                          onChange={(event) => updateDate(item.id, "date", event.target.value)}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`blocked-reason-${item.id}`}>Reason</Label>
                        <Input
                          id={`blocked-reason-${item.id}`}
                          value={item.reason}
                          onChange={(event) => updateDate(item.id, "reason", event.target.value)}
                          placeholder="Optional reason"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground hover:text-destructive"
                        onClick={() => removeDate(item.id)}
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {error && (
          <Alert variant="destructive" className="mt-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="mt-8 flex gap-3">
          <Button variant="outline" className="flex-1" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button className="flex-1" onClick={() => void handleSave()} disabled={saving || loading}>
            {saving ? "Saving…" : "Save blocked dates"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
