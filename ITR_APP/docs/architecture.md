# TaxRight AI Architecture

## Application

```mermaid
flowchart LR
  C[Client browser] --> N[Next.js on Cloud Run]
  N --> A[Firebase Authentication]
  N --> F[(Firestore)]
  N --> S[Private GCS]
  S --> E[Eventarc]
  E --> W[TaxRight Document Intelligence Agent]
  W --> M[Malware and file validation]
  W --> D[Document AI]
  W --> V[Vertex AI structured extraction]
  W --> T[Deterministic tax rules]
  W --> F
  W --> B[(BigQuery downstream events)]
  R[Human reviewer] --> N
```

## Upload pipeline

```mermaid
sequenceDiagram
  participant U as Authenticated client
  participant N as Next.js
  participant Q as Quarantine GCS
  participant W as Worker
  participant C as Clean GCS
  participant F as Firestore
  U->>N: Request signed upload (metadata + checksum)
  N->>N: Verify token, ownership, rate, MIME and size
  N-->>U: Short-lived V4 upload URL
  U->>Q: Upload directly
  Q-->>W: Object-finalised event
  W->>W: Idempotency, signature, malware and PDF checks
  W->>W: OCR, classification, extraction and validation
  W->>C: Preserve clean renamed copy
  W->>F: Update document state and evidence references
```

## Tax calculation pipeline

```mermaid
flowchart TD
  E[Verified extraction fields] --> R[Reconciliation]
  R --> H[Input hash]
  H --> O[Old-regime deterministic engine]
  H --> N[New-regime deterministic engine]
  O --> X[Versioned calculation snapshot + trace]
  N --> X
  X --> F[(Firestore)]
  X --> B[(BigQuery event)]
  X --> V[Human review]
```

## Consent lifecycle

```mermaid
stateDiagram-v2
  [*] --> Presented
  Presented --> Accepted: affirmative action
  Accepted --> VersionSuperseded: notice changes
  Accepted --> Withdrawn: accessible withdrawal
  VersionSuperseded --> Presented
  Withdrawn --> RetentionReview: assess legal obligations
```

## Staff review

```mermaid
flowchart LR
  Q[Review queue] --> P[Secure preview]
  P --> L[Line-level fields]
  L --> A{Reviewer decision}
  A -->|approve| V[Verified]
  A -->|amend| M[Amended + audit event]
  A -->|reject| R[Rejected]
  A -->|more evidence| C[Client action required]
```

## Trust boundaries

- Browser input, file metadata, uploaded bytes, OCR text, and AI output are untrusted.
- Browser never receives service-account credentials, bucket paths, raw PAN indices, or BigQuery access.
- Next.js verifies Firebase tokens and case ownership for every protected request.
- Worker identities are separate from web identities and receive only bucket/collection permissions needed for their tasks.
- Existing income-tax and trust-document storage is read-only reference data and is not copied into development.

## Document Intelligence Agent

```mermaid
flowchart TD
  U[Authenticated metadata] --> Q[Private quarantine object]
  Q --> E[Eventarc finalize event]
  E --> I[Generation idempotency]
  I --> S[Signature, PDF and malware checks]
  S --> H[SHA-256 and duplicate detection]
  H --> C[Deterministic classification]
  C --> P[pdfplumber text extraction]
  P -->|insufficient embedded text| O[Document AI OCR]
  P -->|usable text| X
  O --> V[Optional structured Vertex analysis]
  V --> X[Provenance extraction and validation]
  X --> A{AIS / TIS / 26AS?}
  A -->|yes| R[Normalize and reconcile]
  A -->|no| M[Candidate evidence mapping]
  R --> N[Standard filename]
  M --> N
  N --> G[Immutable original and clean copy]
  G --> F[(Firestore and review tasks)]
  G --> B[(BigQuery events)]
```

The agent has no credential-vault, e-Filing password, OTP, EVC, or filing-session
access. AIS password candidates may only come from versioned verified conventions,
are derived in memory, and are never logged or persisted. The convention list starts
empty and fails closed.
