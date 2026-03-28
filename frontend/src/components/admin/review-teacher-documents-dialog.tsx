"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { apiClient } from "@/lib/api";
import { getVerificationDocumentLabel } from "@/lib/teacher-documents";
import type { VerificationDocument } from "@/types";

interface TeacherVerificationDetail {
  id: string;
  userId: string;
  firstName: string;
  lastName: string;
  email: string;
  verificationStatus: string;
  isListed: boolean;
  isPremium: boolean;
  totalLessons: number;
  hourlyRateCents: number | null;
  province: string | null;
  subjectCount: number;
  subjects: string[];
  documents: VerificationDocument[];
  approvedDocumentCount: number;
  pendingDocumentCount: number;
  rejectedDocumentCount: number;
  allRequiredDocumentsUploaded: boolean;
  allRequiredDocumentsApproved: boolean;
  missingRequiredDocumentTypes: string[];
  rejectedRequiredDocumentTypes: string[];
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  approved: "default",
  rejected: "destructive",
  verified: "default",
  under_review: "outline",
  suspended: "destructive",
};

function formatTimestamp(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-ZA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? fallback;
}

interface ReviewTeacherDocumentsDialogProps {
  teacherId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function ReviewTeacherDocumentsDialog({
  teacherId,
  open,
  onOpenChange,
  onUpdated,
}: ReviewTeacherDocumentsDialogProps) {
  const [detail, setDetail] = useState<TeacherVerificationDetail | null>(null);
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [decisionNotes, setDecisionNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.admin.getTeacherVerification(teacherId);
      const nextDetail = data as TeacherVerificationDetail;
      setDetail(nextDetail);
      setNoteDrafts(
        Object.fromEntries(
          nextDetail.documents.map((document) => [
            document.id,
            document.reviewerNotes ?? "",
          ])
        )
      );
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not load verification details."));
    } finally {
      setLoading(false);
    }
  }, [teacherId]);

  useEffect(() => {
    if (!open || !teacherId) return;
    void loadDetail();
  }, [open, teacherId, loadDetail]);

  useEffect(() => {
    if (!open) {
      setDetail(null);
      setNoteDrafts({});
      setDecisionNotes("");
      setMessage(null);
      setError(null);
      setBusyKey(null);
    }
  }, [open]);

  async function handleOpenDocument(documentId: string) {
    if (!teacherId) return;
    setBusyKey(`view-${documentId}`);
    setError(null);
    try {
      const { data } = await apiClient.admin.getTeacherDocumentAccess(teacherId, documentId);
      window.open((data as { url: string }).url, "_blank", "noopener,noreferrer");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not open this document."));
    } finally {
      setBusyKey(null);
    }
  }

  async function handleReviewDocument(documentId: string, status: "approved" | "rejected") {
    if (!teacherId) return;
    setBusyKey(`${status}-${documentId}`);
    setError(null);
    setMessage(null);
    try {
      await apiClient.admin.reviewTeacherDocument(teacherId, documentId, {
        status,
        reviewer_notes: noteDrafts[documentId]?.trim() || undefined,
      });
      await loadDetail();
      onUpdated();
      setMessage(
        status === "approved"
          ? "Document approved."
          : "Document rejected with reviewer notes."
      );
    } catch (err: unknown) {
      setError(
        getErrorMessage(
          err,
          status === "approved"
            ? "Could not approve this document."
            : "Could not reject this document."
        )
      );
    } finally {
      setBusyKey(null);
    }
  }

  async function handleTeacherDecision(action: "verify" | "reject" | "suspend") {
    if (!teacherId) return;
    setBusyKey(`decision-${action}`);
    setError(null);
    setMessage(null);
    try {
      await apiClient.admin.verifyTeacher(teacherId, {
        action,
        notes: decisionNotes.trim() || undefined,
      });
      await loadDetail();
      onUpdated();
      setMessage(
        action === "verify"
          ? "Teacher verified."
          : action === "reject"
            ? "Teacher rejected."
            : "Teacher suspended."
      );
    } catch (err: unknown) {
      setError(getErrorMessage(err, `Could not ${action} this teacher.`));
    } finally {
      setBusyKey(null);
    }
  }

  const summaryBadges = detail ? [
    { label: `${detail.approvedDocumentCount} approved`, variant: "default" as const },
    { label: `${detail.pendingDocumentCount} pending`, variant: "secondary" as const },
    { label: `${detail.rejectedDocumentCount} rejected`, variant: "destructive" as const },
  ] : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Review Verification Documents</DialogTitle>
          <DialogDescription>
            {detail
              ? `${detail.firstName} ${detail.lastName} · ${detail.email}`
              : "Load the teacher's uploaded documents, leave notes, and decide verification."}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-sm text-muted-foreground">Loading verification details…</div>
        ) : detail ? (
          <div className="space-y-4">
            {(message || error) && (
              <Alert variant={error ? "destructive" : "default"}>
                <AlertDescription>{error ?? message}</AlertDescription>
              </Alert>
            )}

            <div className="rounded-lg border border-border/70 bg-muted/30 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-base font-medium">
                      {detail.firstName} {detail.lastName}
                    </span>
                    <Badge variant={STATUS_VARIANT[detail.verificationStatus] ?? "outline"}>
                      {detail.verificationStatus}
                    </Badge>
                    {detail.isPremium && <Badge variant="outline">Premium</Badge>}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Subjects: {detail.subjects.length ? detail.subjects.join(", ") : "None yet"}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {summaryBadges.map((badge) => (
                      <Badge key={badge.label} variant={badge.variant}>
                        {badge.label}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="text-sm text-muted-foreground">
                  <p>Required docs uploaded: {detail.allRequiredDocumentsUploaded ? "Yes" : "No"}</p>
                  <p>Required docs approved: {detail.allRequiredDocumentsApproved ? "Yes" : "No"}</p>
                </div>
              </div>

              {(detail.missingRequiredDocumentTypes.length > 0 || detail.rejectedRequiredDocumentTypes.length > 0) && (
                <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                  {detail.missingRequiredDocumentTypes.length > 0 && (
                    <p>
                      Missing required types:{" "}
                      {detail.missingRequiredDocumentTypes.map(getVerificationDocumentLabel).join(", ")}
                    </p>
                  )}
                  {detail.rejectedRequiredDocumentTypes.length > 0 && (
                    <p>
                      Rejected and still awaiting replacement:{" "}
                      {detail.rejectedRequiredDocumentTypes.map(getVerificationDocumentLabel).join(", ")}
                    </p>
                  )}
                </div>
              )}

              <div className="mt-4 space-y-2">
                <label className="text-sm font-medium">Overall decision notes</label>
                <Textarea
                  value={decisionNotes}
                  onChange={(event) => setDecisionNotes(event.target.value)}
                  placeholder="Optional note sent when rejecting or suspending the teacher..."
                />
              </div>
            </div>

            <ScrollArea className="max-h-[50vh] rounded-lg border border-border/70">
              <div className="space-y-3 p-4">
                {detail.documents.map((document) => (
                  <div key={document.id} className="rounded-lg border border-border/70 bg-background p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {getVerificationDocumentLabel(document.documentType)}
                          </span>
                          <Badge variant={STATUS_VARIANT[document.status] ?? "outline"}>
                            {document.status}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          <p>{document.fileName}</p>
                          <p>Uploaded: {formatTimestamp(document.createdAt)}</p>
                          <p>Reviewed: {formatTimestamp(document.reviewedAt)}</p>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={busyKey === `view-${document.id}`}
                        onClick={() => handleOpenDocument(document.id)}
                      >
                        {busyKey === `view-${document.id}` ? "Opening…" : "View document"}
                      </Button>
                    </div>

                    <div className="mt-4 space-y-2">
                      <label className="text-sm font-medium">Reviewer notes</label>
                      <Textarea
                        value={noteDrafts[document.id] ?? ""}
                        onChange={(event) =>
                          setNoteDrafts((current) => ({
                            ...current,
                            [document.id]: event.target.value,
                          }))
                        }
                        placeholder="Explain what was checked or what needs to be fixed..."
                      />
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="default"
                        disabled={busyKey === `approved-${document.id}`}
                        onClick={() => handleReviewDocument(document.id, "approved")}
                      >
                        {busyKey === `approved-${document.id}` ? "Approving…" : "Approve"}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="destructive"
                        disabled={busyKey === `rejected-${document.id}`}
                        onClick={() => handleReviewDocument(document.id, "rejected")}
                      >
                        {busyKey === `rejected-${document.id}` ? "Rejecting…" : "Reject"}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        ) : (
          <div className="py-8 text-sm text-muted-foreground">
            No verification details loaded.
          </div>
        )}

        <DialogFooter showCloseButton>
          <Button
            type="button"
            variant="outline"
            disabled={!detail || busyKey === "decision-suspend"}
            onClick={() => void handleTeacherDecision("suspend")}
          >
            {busyKey === "decision-suspend" ? "Suspending…" : "Suspend"}
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={!detail || busyKey === "decision-reject"}
            onClick={() => void handleTeacherDecision("reject")}
          >
            {busyKey === "decision-reject" ? "Rejecting…" : "Reject teacher"}
          </Button>
          <Button
            type="button"
            disabled={!detail || !detail.allRequiredDocumentsApproved || busyKey === "decision-verify"}
            onClick={() => void handleTeacherDecision("verify")}
          >
            {busyKey === "decision-verify" ? "Verifying…" : "Verify teacher"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
