import type { VerificationDocument, VerificationDocumentType } from "@/types";

export const REQUIRED_VERIFICATION_DOCUMENTS: ReadonlyArray<{
  value: VerificationDocumentType;
  label: string;
}> = [
  { value: "id_document", label: "ID Document" },
  { value: "qualification", label: "Qualification Certificate" },
  { value: "sace_certificate", label: "SACE Certificate" },
  { value: "nrso_clearance", label: "NRSO Clearance" },
  { value: "reference_letter", label: "Reference Letter" },
];

function hasUsableDocument(
  documents: VerificationDocument[],
  documentType: VerificationDocumentType
): boolean {
  return documents.some(
    (document) =>
      document.documentType === documentType && document.status !== "rejected"
  );
}

export function hasUploadedAllRequiredDocuments(
  documents: VerificationDocument[]
): boolean {
  return REQUIRED_VERIFICATION_DOCUMENTS.every((document) =>
    hasUsableDocument(documents, document.value)
  );
}

export function getMissingRequiredDocumentTypes(
  documents: VerificationDocument[]
): VerificationDocumentType[] {
  return REQUIRED_VERIFICATION_DOCUMENTS
    .filter((document) => !hasUsableDocument(documents, document.value))
    .map((document) => document.value);
}
