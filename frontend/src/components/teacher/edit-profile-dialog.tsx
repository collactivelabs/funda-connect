"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { apiClient } from "@/lib/api";
import { useReferenceData } from "@/lib/reference-data";
import type { ApiError, Curriculum, TeacherProfile } from "@/types";
import type { AxiosError } from "axios";
const PROVINCES = [
  "Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal",
  "Limpopo", "Mpumalanga", "North West", "Northern Cape", "Western Cape",
];

interface EditProfileDialogProps {
  profile: TeacherProfile;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (updated: TeacherProfile) => void;
}

export function EditProfileDialog({ profile, open, onOpenChange, onSaved }: EditProfileDialogProps) {
  const { curricula, error: referenceDataError } = useReferenceData();
  const [bio, setBio] = useState(profile.bio ?? "");
  const [headline, setHeadline] = useState(profile.headline ?? "");
  const [yearsExperience, setYearsExperience] = useState(
    profile.yearsExperience != null ? String(profile.yearsExperience) : ""
  );
  const [rateRands, setRateRands] = useState(
    profile.hourlyRateCents ? String(Math.round(profile.hourlyRateCents / 100)) : ""
  );
  const [selectedCurricula, setSelectedCurricula] = useState<Set<Curriculum>>(
    new Set(profile.curricula as Curriculum[])
  );
  const [province, setProvince] = useState(profile.province ?? "");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Re-sync when profile changes externally
  useEffect(() => {
    setBio(profile.bio ?? "");
    setHeadline(profile.headline ?? "");
    setYearsExperience(profile.yearsExperience != null ? String(profile.yearsExperience) : "");
    setRateRands(profile.hourlyRateCents ? String(Math.round(profile.hourlyRateCents / 100)) : "");
    setSelectedCurricula(new Set(profile.curricula as Curriculum[]));
    setProvince(profile.province ?? "");
  }, [profile]);

  function toggleCurriculum(c: Curriculum) {
    setSelectedCurricula((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c); else next.add(c);
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const body: Record<string, unknown> = {};
      if (bio !== (profile.bio ?? "")) body.bio = bio || null;
      if (headline !== (profile.headline ?? "")) body.headline = headline || null;
      if (yearsExperience) body.years_experience = Number(yearsExperience);
      if (rateRands) body.hourly_rate_cents = Math.round(Number(rateRands) * 100);
      body.curricula = Array.from(selectedCurricula);
      if (province) body.province = province;

      const { data } = await apiClient.teachers.updateProfile(body);
      onSaved(data as TeacherProfile);
      onOpenChange(false);
    } catch (err) {
      const axiosErr = err as AxiosError<ApiError>;
      setError(axiosErr.response?.data?.detail ?? "Failed to save profile.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Profile</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="ep-headline">Headline</Label>
            <Input
              id="ep-headline"
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              placeholder="e.g. Passionate Maths & Science tutor with 8 years experience"
              maxLength={200}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ep-bio">Bio</Label>
            <Textarea
              id="ep-bio"
              rows={5}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="Tell parents about your teaching approach, qualifications, and specialities…"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ep-rate">Hourly rate (R)</Label>
              <Input
                id="ep-rate"
                type="number"
                min={50}
                max={5000}
                step={10}
                value={rateRands}
                onChange={(e) => setRateRands(e.target.value)}
                placeholder="e.g. 350"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ep-exp">Years experience</Label>
              <Input
                id="ep-exp"
                type="number"
                min={0}
                max={50}
                value={yearsExperience}
                onChange={(e) => setYearsExperience(e.target.value)}
                placeholder="e.g. 5"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Curricula</Label>
            <div className="flex gap-3">
              {curricula.map((curriculumOption) => (
                <label key={curriculumOption.code} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedCurricula.has(curriculumOption.code as Curriculum)}
                    onChange={() => toggleCurriculum(curriculumOption.code as Curriculum)}
                    className="h-4 w-4 rounded border"
                  />
                  <span className="text-sm">{curriculumOption.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ep-province">Province</Label>
            <Select value={province} onValueChange={(v) => setProvince(v ?? "")}>
              <SelectTrigger id="ep-province">
                <SelectValue placeholder="Select province" />
              </SelectTrigger>
              <SelectContent>
                {PROVINCES.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
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
              {loading ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
