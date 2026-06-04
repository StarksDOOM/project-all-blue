/** Phase 4–5 transaction API shapes (storefront source of truth for UI state). */

export type TransactionSessionStatus =
  | "DRAFT"
  | "REVIEW"
  | "GENERATED"
  | "EXECUTED";

export type SignatureRole = "BUYER" | "SELLER";

export interface TransactionRecord {
  id: string;
  property_id: string;
  property_remote_id?: string | null;
  property_title?: string | null;
  buyer_name: string;
  buyer_id_doc: string;
  seller_name: string;
  seller_id_doc: string;
  agreed_price: number;
  currency: string;
  status: TransactionSessionStatus;
  created_at: string;
  updated_at: string;
  buyer_signed_at: string | null;
  seller_signed_at: string | null;
  signature_telemetry: Record<string, unknown>;
  is_locked: boolean;
}

export interface LegalContractRecord {
  id: string;
  transaction_session_id: string;
  file_path: string | null;
  storage_url: string | null;
  document_body: string;
  generated_at: string;
  version_hash: string;
  document_hash?: string | null;
  pdf_file_path?: string | null;
  has_secure_pdf?: boolean;
  docusign_envelope_id?: string | null;
  docusign_status?: string | null;
  has_audit_certificate?: boolean;
  audit_certificate_path?: string | null;
  transaction: TransactionRecord;
  property: {
    id: string;
    remote_id: string;
    title: string;
    sector: string;
    province: string;
    bathrooms: number;
    bedrooms: number;
    square_meters: number;
    sqm_land: number | null;
  };
}

export function isDocumentCryptographicallyLocked(
  status: TransactionSessionStatus
): boolean {
  return status === "GENERATED" || status === "EXECUTED";
}