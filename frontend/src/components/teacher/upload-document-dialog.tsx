"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  REQUIRED_VERIFICATION_DOCUMENTS,
  getVerificationDocumentLabel,
  getMissingRequiredDocumentTypes,
  hasUploadedAllRequiredDocuments,
} from "@/lib/teacher-documents";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import type { VerificationDocument } from "@/types";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  approved: "default",
  rejected: "destructive",
};

interface UploadDocumentDialogProps {
  documents: VerificationDocument[];
  onDocumentsChange: (documents: VerificationDocument[]) => void;
}

export function UploadDocumentDialog({
  documents,
  onDocumentsChange,
}: UploadDocumentDialogProps) {
  const [open, setOpen] = useState(false);
  const [docType, setDocType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [openingDocumentId, setOpeningDocumentId] = useState<string | null>(null);
  const [uploadedDocuments, setUploadedDocuments] = useState<VerificationDocument[]>(documents);
  const fileRef = useRef<HTMLInputElement>(null);

  const missingDocumentTypes = new Set(getMissingRequiredDocumentTypes(uploadedDocuments));
  const availableDocumentTypes = REQUIRED_VERIFICATION_DOCUMENTS.filter((document) =>
    missingDocumentTypes.has(document.value)
  );
  const allRequiredUploaded = hasUploadedAllRequiredDocuments(uploadedDocuments);

  useEffect(() => {
    setUploadedDocuments(documents);
  }, [documents]);

  useEffect(() => {
    if (docType && !availableDocumentTypes.some((document) => document.value === docType)) {
      setDocType("");
    }
  }, [docType, availableDocumentTypes]);

  useEffect(() => {
    if (open) {
      apiClient.teachers.listDocuments()
        .then(({ data }) => {
          const nextDocuments = data as VerificationDocument[];
          setUploadedDocuments(nextDocuments);
          onDocumentsChange(nextDocuments);
        })
        .catch(() => null);
    }
  }, [open, onDocumentsChange]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!docType) { setError("Select a document type."); return; }
    if (!file) { setError("Select a file to upload."); return; }

    setError("");
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await apiClient.teachers.uploadDocument(docType, form);
      const nextDocuments = [data as VerificationDocument, ...uploadedDocuments];
      setUploadedDocuments(nextDocuments);
      onDocumentsChange(nextDocuments);
      setDocType("");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail ?? "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleOpenDocument(documentId: string) {
    setOpeningDocumentId(documentId);
    setError("");
    try {
      const { data } = await apiClient.teachers.getDocumentAccess(documentId);
      window.open((data as { url: string }).url, "_blank", "noopener,noreferrer");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail ?? "Could not open this document.");
    } finally {
      setOpeningDocumentId(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" type="button" />}>
        {allRequiredUploaded ? "View documents" : "Upload documents"}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Verification Documents</DialogTitle>
        </DialogHeader>

        {/* Existing documents */}
        {uploadedDocuments.length > 0 && (
          <div className="space-y-2 mb-2">
            {uploadedDocuments.map((doc) => (
              <div key={doc.id} className="rounded-lg border border-border/70 px-3 py-2">
                <div className="flex items-start justify-between gap-3 text-sm">
                  <div className="min-w-0 space-y-1">
                    <p className="font-medium">{getVerificationDocumentLabel(doc.documentType)}</p>
                    <p className="truncate text-xs text-muted-foreground">{doc.fileName}</p>
                    <p className="text-xs text-muted-foreground">
                      Uploaded: {new Date(doc.createdAt).toLocaleDateString("en-ZA")}
                    </p>
                    {doc.reviewerNotes && (
                      <p className="text-xs text-muted-foreground">
                        Review note: {doc.reviewerNotes}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <Badge variant={STATUS_VARIANT[doc.status] ?? "outline"} className="text-xs">
                      {doc.status}
                    </Badge>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      disabled={openingDocumentId === doc.id}
                      onClick={() => void handleOpenDocument(doc.id)}
                    >
                      {openingDocumentId === doc.id ? "Opening…" : "View"}
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {allRequiredUploaded ? (
          <div className="border-t pt-4">
            <p className="text-sm text-muted-foreground">
              All five required document types have been uploaded. Your verification submission is ready for admin review.
            </p>
          </div>
        ) : (
          <form onSubmit={handleUpload} className="space-y-4 border-t pt-4">
            <div className="space-y-2">
              <Label>Document type</Label>
              <Select value={docType} onValueChange={(v) => setDocType(v ?? "")}>
                <SelectTrigger>
                  <SelectValue placeholder="Select type…" />
                </SelectTrigger>
                <SelectContent>
                  {availableDocumentTypes.map((document) => (
                    <SelectItem key={document.value} value={document.value}>{document.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="doc-file">File (PDF, JPG, PNG — max 10 MB)</Label>
              <input
                id="doc-file"
                ref={fileRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1 file:text-sm file:font-medium"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex justify-end">
              <Button type="submit" disabled={loading}>
                {loading ? "Uploading…" : "Upload"}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
