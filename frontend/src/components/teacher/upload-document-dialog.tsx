"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  REQUIRED_VERIFICATION_DOCUMENTS,
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

  function labelFor(type: string) {
    return REQUIRED_VERIFICATION_DOCUMENTS.find((document) => document.value === type)?.label ?? type;
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
              <div key={doc.id} className="flex items-center justify-between text-sm py-1">
                <span className="text-muted-foreground truncate mr-2">{labelFor(doc.documentType)}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-muted-foreground truncate max-w-32">{doc.fileName}</span>
                  <Badge variant={STATUS_VARIANT[doc.status] ?? "outline"} className="text-xs">
                    {doc.status}
                  </Badge>
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
