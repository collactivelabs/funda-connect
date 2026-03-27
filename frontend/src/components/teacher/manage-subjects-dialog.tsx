"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import type { ApiError, Subject, TeacherSubject } from "@/types";
import type { AxiosError } from "axios";

const CURRICULA = ["CAPS", "Cambridge", "IEB"];
const GRADES = [
  "Grade R",
  "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6",
  "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12",
];

interface ManageSubjectsDialogProps {
  teacherSubjects: TeacherSubject[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged: (subjects: TeacherSubject[]) => void;
}

export function ManageSubjectsDialog({
  teacherSubjects,
  open,
  onOpenChange,
  onChanged,
}: ManageSubjectsDialogProps) {
  const [allSubjects, setAllSubjects] = useState<Subject[]>([]);
  const [subjectsLoading, setSubjectsLoading] = useState(false);
  const [subjectsError, setSubjectsError] = useState<string | null>(null);
  const [current, setCurrent] = useState<TeacherSubject[]>(teacherSubjects);
  const [subjectId, setSubjectId] = useState("");
  const [curriculum, setCurriculum] = useState("");
  const [selectedGrades, setSelectedGrades] = useState<Set<string>>(new Set());
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  useEffect(() => {
    setCurrent(teacherSubjects);
  }, [teacherSubjects]);

  useEffect(() => {
    if (!open) return;
    setSubjectsLoading(true);
    setSubjectsError(null);
    apiClient.subjects.list()
      .then(({ data }) => setAllSubjects(data as Subject[]))
      .catch(() => {
        setAllSubjects([]);
        setSubjectsError("Failed to load subjects.");
      })
      .finally(() => setSubjectsLoading(false));
  }, [open]);

  function toggleGrade(g: string) {
    setSelectedGrades((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g); else next.add(g);
      return next;
    });
  }

  async function handleAdd() {
    if (!subjectId || !curriculum || selectedGrades.size === 0) {
      setAddError("Please select a subject, curriculum, and at least one grade.");
      return;
    }
    setAddError(null);
    setAdding(true);
    try {
      const { data } = await apiClient.teachers.addSubject({
        subject_id: subjectId,
        curriculum,
        grade_levels: Array.from(selectedGrades),
      });
      const newList = [...current, data as TeacherSubject];
      setCurrent(newList);
      onChanged(newList);
      // Reset add form
      setSubjectId("");
      setCurriculum("");
      setSelectedGrades(new Set());
    } catch (err) {
      const axiosErr = err as AxiosError<ApiError>;
      setAddError(axiosErr.response?.data?.detail ?? "Failed to add subject.");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(id: string) {
    setRemoving(id);
    try {
      await apiClient.teachers.removeSubject(id);
      const newList = current.filter((s) => s.id !== id);
      setCurrent(newList);
      onChanged(newList);
    } catch {
      // silently ignore
    } finally {
      setRemoving(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage Subjects</DialogTitle>
        </DialogHeader>

        {/* Current subjects */}
        {current.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Current subjects</p>
            {current.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-2 py-1">
                <div className="min-w-0">
                  <span className="text-sm font-medium">{s.subjectName}</span>
                  <span className="text-xs text-muted-foreground ml-2">{s.curriculum}</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {s.gradeLevels.map((g) => (
                      <Badge key={g} variant="outline" className="text-xs">{g}</Badge>
                    ))}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="shrink-0 text-destructive hover:text-destructive"
                  disabled={removing === s.id}
                  onClick={() => handleRemove(s.id)}
                >
                  {removing === s.id ? "…" : "Remove"}
                </Button>
              </div>
            ))}
            <Separator />
          </div>
        )}

        {/* Add subject form */}
        <div className="space-y-4">
          <p className="text-sm font-medium">Add a subject</p>

          <div className="space-y-1.5">
            <Label>Subject</Label>
            <Select value={subjectId} onValueChange={(v) => setSubjectId(v ?? "")}>
              <SelectTrigger disabled={subjectsLoading || allSubjects.length === 0}>
                <SelectValue placeholder={subjectsLoading ? "Loading subjects…" : "Select subject"} />
              </SelectTrigger>
              <SelectContent>
                {allSubjects.map((s) => (
                  <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {subjectsError && (
              <p className="text-xs text-destructive">{subjectsError}</p>
            )}
            {!subjectsLoading && !subjectsError && allSubjects.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No subjects are available yet.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Curriculum</Label>
            <Select value={curriculum} onValueChange={(v) => setCurriculum(v ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="Select curriculum" />
              </SelectTrigger>
              <SelectContent>
                {CURRICULA.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Grade levels</Label>
            <div className="flex flex-wrap gap-1.5">
              {GRADES.map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => toggleGrade(g)}
                  className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                    selectedGrades.has(g)
                      ? "bg-primary text-primary-foreground border-primary"
                      : "border-border hover:bg-muted"
                  }`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>

          {addError && (
            <Alert variant="destructive">
              <AlertDescription>{addError}</AlertDescription>
            </Alert>
          )}

          <Button onClick={handleAdd} disabled={adding} className="w-full">
            {adding ? "Adding…" : "Add Subject"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
