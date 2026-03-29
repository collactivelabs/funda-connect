# 08 — Security & POPIA Compliance

> **Status:** Draft  
> **Last Updated:** 2026-03-29

---

## 1. Overview

FundaConnect handles sensitive personal data (identity documents, children's academic records, financial information) and must comply with the Protection of Personal Information Act (POPIA). This document outlines the security architecture, data protection measures, and compliance obligations.

### 1.1 Implementation Snapshot

As of **2026-03-29**, the live backend already enforces:
- CORS allow-listing for configured origins
- Security response headers for all API responses
- Conditional HSTS in production
- Redis-backed rate limiting on key auth, booking, upload, and admin mutation endpoints
- Consent tracking for terms, privacy policy, and marketing preferences
- Signed document upload validation for PDF/JPEG/PNG files using magic bytes, size limits, and safe filename normalisation
- Optional ClamAV (`clamscan`) malware scanning for uploads when configured
- Audit logging for key admin decisions, private document access, booking lifecycle changes, and PayFast ITN state changes
- Account data export via `/account/data-export`
- Account deletion requests with immediate deactivation, future booking cancellation, 30-day anonymisation scheduling, and a daily anonymisation sweep

The following areas are still backlog items rather than completed guarantees:
- Cross-provider malware scanning/quarantine beyond the current optional ClamAV path

---

## 2. Data Classification

| Classification | Examples | Storage | Access | Retention |
|---------------|----------|---------|--------|-----------|
| **Critical** | Passwords, payment tokens, API keys | Hashed/encrypted; never logged | System only | Duration of use |
| **Sensitive** | ID documents, NRSO clearance, bank details | Encrypted at rest (AES-256) | Teacher (own) + Admin | Account lifetime + 2 years |
| **Personal** | Names, email, phone, learner profiles | Encrypted at rest | User (own) + Admin | Account lifetime + 1 year |
| **Internal** | Booking records, lesson logs, reviews | Standard DB storage | Users (own) + Admin | 5 years (audit) |
| **Public** | Teacher public profiles, subject listings | Standard DB storage | Everyone | Indefinite |

---

## 3. Encryption

### 3.1 Data in Transit
- **TLS 1.3** enforced on all connections (API, web, database)
- HSTS enabled with `max-age=31536000; includeSubDomains; preload`
- Certificate management via Let's Encrypt (auto-renewal)
- API enforces HTTPS; HTTP requests redirected

### 3.2 Data at Rest
- **Database:** PostgreSQL Transparent Data Encryption (TDE) or AWS RDS encryption
- **File Storage:** S3 server-side encryption (SSE-S3 or SSE-KMS)
- **Backups:** Encrypted with separate key from primary storage
- **Redis:** Configured with TLS for data in transit; `requirepass` for access control

### 3.3 Application-Level Encryption
```python
from cryptography.fernet import Fernet

# Sensitive fields (e.g., SACE number, bank details) encrypted before DB storage
class EncryptionService:
    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()
```

### 3.4 Password Storage
- **Algorithm:** bcrypt with 12 rounds
- **Pepper:** Application-secret prepended before hashing
- Passwords never logged, cached, or stored in plaintext

---

## 4. POPIA Compliance

### 4.1 Lawful Processing Conditions

FundaConnect processes personal data under the following POPIA conditions:

| Condition | Application |
|-----------|-------------|
| **Consent** | Explicit opt-in during registration; separate consent for marketing communications |
| **Contract** | Processing necessary to perform the service (bookings, payments, lesson delivery) |
| **Legal obligation** | Tax records (SARS), NRSO checks (Children's Act), audit trail |
| **Legitimate interest** | Fraud detection, platform security, service improvement |

### 4.2 Data Subject Rights

FundaConnect must support these POPIA data subject rights:

| Right | Implementation |
|-------|---------------|
| **Right to access** | Users can download their personal account data via `/account/data-export` |
| **Right to correction** | Users can update their profile information; request corrections via support |
| **Right to deletion** | `POST /account/delete-request` deactivates the account, cancels future bookings, revokes sessions, and schedules anonymisation (see §4.4) |
| **Right to object** | Users can opt out of marketing; object to specific processing |
| **Right to restrict** | Users can request temporary halt of processing via support |
| **Right to data portability** | Data export in JSON format |

### 4.3 Privacy Policy Requirements

The published privacy policy must include:
- Identity of the responsible party (FundaConnect Pty Ltd) and Information Officer
- What personal information is collected and from whom
- Purpose of processing for each data category
- Third parties who receive data (PayFast, SMS providers, cloud infrastructure)
- Cross-border data transfers (if cloud hosting is outside SA)
- Data retention periods
- How to exercise data subject rights
- How to lodge a complaint with the Information Regulator
- Cookie policy and tracking technologies used

### 4.4 Account Deletion & Data Removal

```
User requests account deletion:

1. Immediate:
   - Account deactivated (is_active = false)
   - Profile removed from search results
   - Active bookings cancelled with refund
   - Refresh sessions revoked; future access tokens are rejected once the account is inactive
   
2. 30-day grace period:
   - Account remains inactive and inaccessible
   - Anonymisation is scheduled for 30 days after the request

3. After 30 days (automated daily Celery task):
   - Personal identifiers anonymised (name → "Deleted User", email → hash@deleted.local)
   - Profile photo deleted from S3
   - Verification documents deleted from S3 and replaced with tombstone references in the DB
   - Phone number cleared
   - Notifications deleted; legal/audit records retained in anonymised form
   
4. Retained (legal obligation):
   - Anonymised booking records (5 years — tax/audit)
   - Anonymised payment records (5 years — SARS)
   - Audit log entries (5 years)
   
5. After retention period:
   - Anonymised records purged
```

### 4.5 Consent Management

```python
class ConsentRecord:
    user_id: UUID
    consent_type: str       # 'terms_of_service', 'privacy_policy', 'marketing_email', 'marketing_sms'
    granted: bool
    version: str            # policy version consented to
    ip_address: str
    user_agent: str
    granted_at: datetime
    revoked_at: datetime | None
```

- Consent tracked per type with versioning
- Re-consent required when privacy policy is updated
- Marketing consent separate from service consent
- Consent withdrawal processed within 24 hours

Current implementation note:
- Registration records required consent for terms and privacy policy, plus optional marketing email/SMS preferences.
- Users can review and update marketing consent through `/account/consents`.

### 4.6 Information Officer

- The CEO/MD is automatically the Information Officer (IO) per POPIA
- IO registered with the Information Regulator
- Deputy Information Officers (DIOs) may be appointed
- Contact details published in privacy policy and on the platform

---

## 5. Breach Response Plan

### 5.1 Breach Classification

| Severity | Definition | Response Time |
|----------|------------|---------------|
| **Critical** | PII exposed externally; financial data compromised; credentials leaked | Immediate (within 1 hour) |
| **High** | Internal data access by unauthorised employee; system vulnerability exploited | Within 4 hours |
| **Medium** | Attempted breach blocked; suspicious activity detected | Within 24 hours |
| **Low** | Minor policy violation; misconfigured access | Within 72 hours |

### 5.2 Response Procedure

```
1. DETECT & CONTAIN (0-1 hours)
   - Identify scope and affected systems
   - Isolate compromised systems
   - Revoke compromised credentials
   - Preserve forensic evidence
   
2. ASSESS (1-4 hours)
   - Determine what data was affected
   - Identify number of affected data subjects
   - Assess risk to data subjects
   
3. NOTIFY (within 72 hours per POPIA 2025 amendments)
   - Notify the Information Regulator
   - Notify affected data subjects (if risk of harm)
   - Notification must include:
     * Description of the breach
     * Types of personal information involved
     * Measures taken to address the breach
     * Recommendations for data subjects
   
4. REMEDIATE
   - Fix root cause
   - Update security controls
   - Document lessons learned
   - Update breach response plan if needed
```

---

## 6. Application Security

### 6.1 Input Validation
- All inputs validated via Pydantic schemas (FastAPI)
- SQL injection prevention via SQLAlchemy ORM (parameterised queries)
- XSS prevention via React's default escaping + Content Security Policy
- File upload validation currently includes declared-type checks, magic-byte validation, size limits, filename normalisation, and optional `clamscan` malware scanning when configured

### 6.2 API Security
- JWT authentication with short-lived access tokens (30 min)
- CORS configured to allow only known origins
- Security headers added on every response (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, and HSTS in production)
- Redis-backed rate limiting now protects key auth, booking, upload, and admin mutation endpoints
- Request size limits (10MB max body)
- No sensitive data in URL parameters

### 6.3 File Upload Security
```python
ALLOWED_SIGNATURES = {
    "application/pdf": [b"%PDF-"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def validate_upload(contents: bytes, filename: str, declared_content_type: str):
    # 1. Check declared content type
    if declared_content_type not in ALLOWED_SIGNATURES:
        raise ValidationError("File type not allowed")

    # 2. Check file size
    if len(contents) > MAX_FILE_SIZE:
        raise ValidationError("File too large")

    # 3. Validate magic bytes (actual file type)
    if not any(contents.startswith(signature) for signature in ALLOWED_SIGNATURES[declared_content_type]):
        raise ValidationError("File content does not match declared type")

    # 4. Normalise the stored filename
    safe_name = sanitise_filename(filename, declared_content_type)

    return safe_name
```

Current implementation note:
- Document uploads are validated against the declared file type and canonicalised before storage.
- When `MALWARE_SCAN_MODE=clamscan`, uploads are scanned before storage and rejected if ClamAV marks them as infected.
- Full quarantine workflows or third-party scanning providers remain future enhancements.

### 6.4 Dependency Security
- `pip-audit` and `pnpm audit` run in CI pipeline
- Dependabot enabled for automated security updates
- No `*` version pins — all dependencies pinned to specific versions
- Container base images scanned with Trivy

---

## 7. Audit Logging

Implementation snapshot:
- The backend now persists audit records for high-sensitivity actions, including:
  - admin document access/review and teacher verification decisions
  - payout, refund, and dispute resolution actions
  - teacher document uploads and document access
  - booking creation, rescheduling, cancellation, completion, dispute creation, series cancellation, and PayFast ITN status changes
- Each record stores actor role, actor user id when available, resource type/id, request IP, user agent, and structured metadata.

### 7.1 Logged Events

| Category | Events |
|----------|--------|
| **Authentication** | Login success/failure, logout, password change, token refresh |
| **Data Access** | Profile view, document download, report generation |
| **Data Modification** | Profile update, booking create/cancel, review submit |
| **Admin Actions** | Verification approve/reject, user suspend, payout process |
| **Financial** | Payment received, refund issued, payout processed |
| **Security** | Failed login attempts, rate limit hits, suspicious activity |

### 7.2 Audit Log Format

```json
{
  "id": "audit-uuid",
  "timestamp": "2026-03-25T14:30:00Z",
  "user_id": "user-uuid",
  "action": "booking.create",
  "resource_type": "booking",
  "resource_id": "booking-uuid",
  "ip_address": "41.13.xxx.xxx",
  "user_agent": "Mozilla/5.0...",
  "metadata": {
    "teacher_id": "teacher-uuid",
    "amount_cents": 25000
  }
}
```

### 7.3 Log Retention
- Audit logs retained for **5 years** (POPIA and tax compliance)
- Archived to cold storage after 1 year
- Searchable via admin interface (recent 90 days) or on-demand retrieval
- Immutable: audit log records cannot be modified or deleted
