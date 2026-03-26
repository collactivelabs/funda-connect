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
import type { ApiError, Learner } from "@/types";
import type { AxiosError } from "axios";

const GRADES = [
  "Grade R",
  "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6",
  "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12",
];
const CURRICULA = ["CAPS", "Cambridge", "IEB"];

interface AddLearnerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdded: (learner: Learner) => void;
}

export function AddLearnerDialog({ open, onOpenChange, onAdded }: AddLearnerDialogProps) {
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
                {GRADES.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}
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
                {CURRICULA.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
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
