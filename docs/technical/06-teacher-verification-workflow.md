# 06 — Teacher Verification Workflow

> **Status:** Draft  
> **Last Updated:** 2026-03-25

---

## 1. Overview

Teacher verification is a critical trust and safety mechanism. Every teacher must complete a multi-step verification process before their profile becomes visible to parents. The process verifies identity, qualifications, professional registration, and child safety clearance.

---

## 2. Verification State Machine

```
                    ┌──────────┐
                    │ PENDING  │  ← Initial state on registration
                    └────┬─────┘
                         │ Teacher uploads documents
                         ▼
                ┌─────────────────┐
                │   DOCUMENTS     │
                │   SUBMITTED     │
                └────────┬────────┘
                         │ Admin picks up for review
                         ▼
                ┌─────────────────┐
                │  UNDER REVIEW   │
                └───┬─────────┬───┘
                    │         │
            ┌───────▼──┐  ┌───▼────────┐
            │ VERIFIED │  │  REJECTED  │
            └──────────┘  └──────┬─────┘
                                 │ Teacher can re-submit
                                 ▼
                         ┌───────────────┐
                         │   DOCUMENTS   │
                         │   SUBMITTED   │
                         └───────────────┘

        ─── At any time (admin action) ───

            ┌─────────────┐
            │  SUSPENDED  │  ← Admin can suspend any verified teacher
            └─────────────┘
```

### Valid Transitions

| From | To | Trigger |
|------|----|---------|
| `pending` | `documents_submitted` | Teacher uploads all required documents |
| `documents_submitted` | `under_review` | Admin begins review |
| `under_review` | `verified` | Admin approves all documents |
| `under_review` | `rejected` | Admin rejects one or more documents |
| `rejected` | `documents_submitted` | Teacher re-uploads corrected documents |
| `verified` | `suspended` | Admin suspends (policy violation, complaint) |
| `suspended` | `verified` | Admin reinstates |

---

## 3. Required Documents

| # | Document | Type | Validation Criteria |
|---|----------|------|---------------------|
| 1 | **South African ID** | `id_document` | Valid SA ID number; name matches registration; certified copy |
| 2 | **Teaching Qualification** | `qualification` | Degree, diploma, or PGCE from accredited institution; certified copy |
| 3 | **SACE Certificate** | `sace_certificate` | Active registration with SA Council for Educators; valid SACE number |
| 4 | **NRSO Clearance** | `nrso_clearance` | Clearance certificate from National Register for Sex Offenders; mandatory for working with minors |
| 5 | **Professional Reference** | `reference_letter` | At least one reference from a school, university, or education institution |

### Document Upload Rules
- **Accepted formats:** PDF, JPG, PNG
- **Maximum file size:** 10MB per document
- **Storage:** Encrypted at rest in S3/B2 with restricted access
- **Retention:** Documents retained for the duration of the teacher's account + 2 years after deactivation (POPIA compliance)
- **Access:** Only the teacher (own documents) and admins can view uploaded documents

---

## 4. Verification Process (Detailed)

### Step 1: Teacher Registration
```
Teacher registers with role="teacher"
→ User record created
→ Teacher profile created with verification_status = "pending"
→ Welcome email sent with onboarding guide
```

### Step 2: Document Upload
```
Teacher navigates to /dashboard/verification
→ Uploads each required document
→ Each document stored in S3 with key: teachers/{teacher_id}/verification/{doc_type}_{timestamp}.pdf
→ verification_documents record created for each (status = "pending")
→ When all 5 required types uploaded: teacher profile → "documents_submitted"
→ Admin notification: "New teacher verification request"
```

### Step 3: Admin Review
```
Admin navigates to /admin/verification/pending
→ Reviews each document:
   - Opens document (presigned S3 URL, expires in 15 min)
   - Checks authenticity and validity
   - Marks each as "approved" or "rejected" with notes
→ If ALL documents approved:
   - Teacher profile → "verified"
   - Teacher profile → verified_at = now()
   - Verification confirmation email sent
   - Profile becomes visible in teacher search
→ If ANY document rejected:
   - Teacher profile → "rejected"
   - Rejection email sent with reasons and resubmission instructions
```

### Step 4: SACE Number Verification (Future Enhancement)
```
When automated SACE API becomes available:
→ Validate SACE number against SACE database
→ Verify name match and active status
→ Flag expired or suspended registrations
```

### Step 5: NRSO Check (Future Enhancement)
```
When automated NRSO check becomes available:
→ Submit teacher ID for NRSO screening
→ Receive clearance status
→ Block teachers with NRSO records
→ Re-check annually
```

---

## 5. Post-Verification Monitoring

### Ongoing Checks
- **Annual re-verification:** Teachers prompted to confirm SACE and NRSO status annually
- **Complaint-triggered review:** If a parent reports a teacher, admin reviews and may suspend pending investigation
- **Rating threshold:** Teachers whose rating drops below 3.0 over 10+ reviews are flagged for admin review
- **No-show monitoring:** 3+ no-shows within 30 days triggers automatic suspension

### Suspension Criteria
| Trigger | Action |
|---------|--------|
| NRSO flag discovered | Immediate suspension; account under review |
| Serious parent complaint | Temporary suspension pending investigation |
| Rating below 3.0 (10+ reviews) | Warning; suspended if not improved in 30 days |
| 3+ no-shows in 30 days | Automatic suspension; can appeal |
| SACE registration expired | Profile hidden until renewed |
| Terms of service violation | Suspension at admin discretion |

---

## 6. Data Model Reference

See `verification_documents` table in [Database Schema](./02-database-schema.md#27-verification_documents).

---

## 7. Admin Dashboard — Verification Queue

The admin verification interface should display:

```
┌─────────────────────────────────────────────────────────┐
│  VERIFICATION QUEUE                          [Filter ▼] │
├─────────────────────────────────────────────────────────┤
│  ⏳ 12 pending  │  🔍 3 under review  │  ✅ 187 verified │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Nomvula M.           Submitted: 2026-03-24             │
│  Subjects: Maths, Science   Province: Gauteng           │
│  Documents: ✅ ID  ✅ Qual  ⏳ SACE  ⏳ NRSO  ⏳ Ref      |
│  [Review Documents]  [Approve All]  [Reject]            │
│                                                         │
│  Thandi K.            Submitted: 2026-03-23             │
│  Subjects: Accounting  Province: KZN                    │
│  Documents: ✅ ID  ✅ Qual  ✅ SACE  ✅ NRSO  ⏳ Ref      │
│  [Review Documents]  [Approve All]  [Reject]            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### SLA Targets
- Document review initiated within **2 business days** of submission
- Full verification decision within **5 business days**
- Rejection notification sent within **1 business day** of decision
