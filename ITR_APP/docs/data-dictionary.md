# Data Dictionary

Classification: `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `HIGHLY_SENSITIVE`.

## Firestore

### `users/{firebaseUid}`

| Field | Type | Classification | Purpose |
|---|---|---|---|
| `uid` | string | INTERNAL | Firebase identity |
| `display_name` | string | CONFIDENTIAL | Client/staff display |
| `role` | enum | INTERNAL | Server-controlled authorization |
| `created_at` | timestamp | INTERNAL | Audit |

### `clients/{clientId}`

| Field | Type | Classification | Purpose |
|---|---|---|---|
| `client_id` | UUIDv7 | INTERNAL | Immutable client identifier |
| `owner_uid` | string | INTERNAL | Authorization link |
| `full_name` | string | CONFIDENTIAL | Taxpayer name |
| `pan_ciphertext` | bytes | HIGHLY_SENSITIVE | Optional encrypted PAN only when operationally required |
| `pan_masked` | string | CONFIDENTIAL | Restricted display |
| `created_at`, `updated_at` | timestamp | INTERNAL | Lifecycle |

### `pan_index/{panFingerprint}`

| Field | Type | Classification | Purpose |
|---|---|---|---|
| document ID | HMAC-SHA256 | HIGHLY_SENSITIVE | Duplicate prevention; server only |
| `client_id` | UUIDv7 | INTERNAL | Atomic client link |
| `created_at` | timestamp | INTERNAL | Audit |

### `cases/{caseId}`

`case_id` (INTERNAL), `friendly_case_number` (INTERNAL), `client_id` (INTERNAL), `owner_uid` (INTERNAL), `assessment_year` (INTERNAL), `status` (INTERNAL), `assigned_staff_id` (INTERNAL), timestamps (INTERNAL).

### Case subcollections

- `documents`: IDs, object references, checksum, MIME, classification, processing status, confidence, provenance and timestamps. Object references are CONFIDENTIAL; extracted taxpayer fields are HIGHLY_SENSITIVE.
- `calculations`: version, rules version, input hash, integer money values, trace and creator. CONFIDENTIAL.
- `deductions`: section, submitted/eligible values, state, reasons and evidence IDs. CONFIDENTIAL.
- `consents`: type/version/notice/accepted/timestamps/minimal IP hash/user-agent family. CONFIDENTIAL.
- `preferences`: independent Grocery/Services/Gold selection and confirmation. CONFIDENTIAL; no donation linkage.
- `reviews`: reviewer decisions and evidence requests. CONFIDENTIAL; staff only.
- `activity`: immutable event identifiers, actors, actions and value hashes. INTERNAL/CONFIDENTIAL; no copied PII.

## BigQuery

The SQL migrations define `clients`, `cases`, `documents`, `document_extractions`, `tax_calculations`, `deduction_findings`, `deduction_evidence`, `consents`, `client_preferences`, `review_tasks`, `audit_events`, and `processing_metrics`.

- Identifiers, statuses, versions, timestamps and metrics are INTERNAL.
- Income, deductions and tax values are CONFIDENTIAL.
- `pan_fingerprint` is HIGHLY_SENSITIVE and must be policy-tagged/restricted.
- Raw PAN, Aadhaar, OCR body, signed URLs and document bytes are prohibited from ordinary analytics tables.

