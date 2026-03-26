"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
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

const DOC_TYPES = [
  { value: "id_document", label: "ID Document" },
  { value: "qualification", label: "Qualification Certificate" },
  { value: "sace_certificate", label: "SACE Certificate" },
  { value: "nrso_clearance", label: "NRSO Clearance" },
  { value: "reference_letter", label: "Reference Letter" },
] as const;

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  approved: "default",
  rejected: "destructive",
};

interface Document {
  id: string;
  document_type: string;
  file_name: string;
  status: string;
}

export function UploadDocumentDialog() {
  const [open, setOpen] = useState(false);
  const [docType, setDocType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      apiClient.teachers.listDocuments()
        .then(({ data }) => setDocuments(data as Document[]))
        .catch(() => null);
    }
  }, [open]);

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
      setDocuments((prev) => [data as Document, ...prev]);
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
    return DOC_TYPES.find((d) => d.value === type)?.label ?? type;
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger>
        <Button variant="outline" size="sm" type="button">
          Upload documents
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Verification Documents</DialogTitle>
        </DialogHeader>

        {/* Existing documents */}
        {documents.length > 0 && (
          <div className="space-y-2 mb-2">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between text-sm py-1">
                <span className="text-muted-foreground truncate mr-2">{labelFor(doc.document_type)}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-muted-foreground truncate max-w-32">{doc.file_name}</span>
                  <Badge variant={STATUS_VARIANT[doc.status] ?? "outline"} className="text-xs">
                    {doc.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleUpload} className="space-y-4 border-t pt-4">
          <div className="space-y-2">
            <Label>Document type</Label>
            <Select value={docType} onValueChange={(v) => setDocType(v ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="Select type…" />
              </SelectTrigger>
              <SelectContent>
                {DOC_TYPES.map((d) => (
                  <SelectItem key={d.value} value={d.value}>{d.label}</SelectItem>
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
      </DialogContent>
    </Dialog>
  );
}
