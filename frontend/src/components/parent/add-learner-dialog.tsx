"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { apiClient } from "@/lib/api";
import { useReferenceData } from "@/lib/reference-data";
import type { ApiError, Learner } from "@/types";
import type { AxiosError } from "axios";

interface AddLearnerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdded: (learner: Learner) => void;
}

export function AddLearnerDialog({ open, onOpenChange, onAdded }: AddLearnerDialogProps) {
  const { curricula, gradeLevels, error: referenceDataError } = useReferenceData();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [grade, setGrade] = useState("");
  const [curriculum, setCurriculum] = useState("");
  const [age, setAge] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function reset() {
    setFirstName("");
    setLastName("");
    setGrade("");
    setCurriculum("");
    setAge("");
    setNotes("");
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await apiClient.parents.createLearner({
        first_name: firstName,
        last_name: lastName,
        grade,
        curriculum,
        age: age ? Number(age) : undefined,
        notes: notes || undefined,
      });
      onAdded(data as Learner);
      onOpenChange(false);
      reset();
    } catch (err) {
      const axiosErr = err as AxiosError<ApiError>;
      setError(axiosErr.response?.data?.detail ?? "Failed to add learner. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); onOpenChange(v); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add a Learner</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="add-first-name">First name *</Label>
              <Input
                id="add-first-name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="add-last-name">Last name *</Label>
              <Input
                id="add-last-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="add-grade">Grade *</Label>
            <Select value={grade} onValueChange={(v) => setGrade(v ?? "")} required>
              <SelectTrigger id="add-grade">
                <SelectValue placeholder="Select grade" />
              </SelectTrigger>
              <SelectContent>
                {gradeLevels.map((gradeOption) => (
                  <SelectItem key={gradeOption.value} value={gradeOption.value}>{gradeOption.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="add-curriculum">Curriculum *</Label>
            <Select value={curriculum} onValueChange={(v) => setCurriculum(v ?? "")} required>
              <SelectTrigger id="add-curriculum">
                <SelectValue placeholder="Select curriculum" />
              </SelectTrigger>
              <SelectContent>
                {curricula.map((curriculumOption) => (
                  <SelectItem key={curriculumOption.code} value={curriculumOption.code}>{curriculumOption.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="add-age">Age (optional)</Label>
            <Input
              id="add-age"
              type="number"
              min={3}
              max={25}
              value={age}
              onChange={(e) => setAge(e.target.value)}
              placeholder="e.g. 12"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="add-notes">Notes (optional)</Label>
            <Textarea
              id="add-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Learning goals, special requirements, etc."
            />
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {!error && referenceDataError && (
            <Alert>
              <AlertDescription>{referenceDataError}</AlertDescription>
            </Alert>
          )}

          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" className="flex-1" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" disabled={loading}>
              {loading ? "Adding…" : "Add Learner"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
