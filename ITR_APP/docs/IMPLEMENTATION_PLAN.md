# TaxRight AI Implementation Plan

Last updated: 2026-08-17

## Current build status

- Architecture/governance documentation: implemented.
- Next.js product foundation and responsive client/staff experience: implemented.
- Identity, PAN fingerprint, roles, logging redaction, consent schemas and state machine: implemented.
- Deterministic AY 2026-27 baseline and 80G engine: implemented with engineering tests; **tax-professional sign-off remains required**.
- Authenticated API contracts: implemented; live Firebase/GCP persistence intentionally fails closed until configuration is approved.
- Firestore rules/indexes, BigQuery DDL, Terraform, Docker and Cloud Build definitions: implemented but unapplied.
- Unit/security tests: 15 passing.
- Production browser smoke tests: 4 passing across Chromium desktop and WebKit mobile.
- Dependency audit: zero known vulnerabilities after patched transitive override.
- Production build: passing on Next.js 16.3.1.

The full cloud document pipeline, live Firebase providers, malware service, Document AI processors, Vertex models, BigQuery policy identities, Cloud Run worker deployment, and staging environment cannot be activated safely without the manual prerequisites and explicit infrastructure approval listed below.

## Delivery principles

- Treat PAN, Aadhaar, tax documents, financial records, signed URLs, and OCR text as highly sensitive.
- Keep Firestore as the operational source of truth; BigQuery receives downstream events only.
- Preserve original evidence and maintain immutable provenance.
- Make tax calculations deterministic, versioned, evidence-linked, and human-reviewed.
- Treat uploaded document content as untrusted input, including prompt-injection attempts.
- Do not deploy, apply Terraform, enable billable APIs, or mutate existing GCP resources without explicit approval.

## Phase 1 — Discovery (complete)

- Existing repository: FastAPI backend (`itr_backend`), document/tax Python agent (`itr_agent`), and minimal Next.js App Router frontend (`web`).
- Existing frontend baseline: Next.js 16.2.12, React 19.2.8, strict TypeScript.
- Verified current stable Next.js: 16.2.12 from the npm latest tag on 2026-08-17.
- Toolchain: Node 24.18.0, npm 12.0.1; pnpm is unavailable.
- Git: clean working tree before this project; four existing commits, latest `064acd5`.
- GCP project: `aidirac-503309`.
- Firestore: `(default)`, Native mode, `asia-south1`, pessimistic concurrency, delete protection disabled.
- Buckets: private income-tax bucket, `chennaifood`, and Cloud Run sources bucket. Public access prevention is enforced on the income-tax bucket.
- Existing income-tax prefixes include `Trust_details/`; this storage remains read-only for TaxRight unless separately authorised.
- Existing BigQuery operations dataset is documented as `income_tax_ops` in `asia-south1`.
- Existing Cloud Run services are unrelated to TaxRight; no TaxRight service exists.
- Firebase web configuration, Firebase Authentication providers, App Check, Document AI processors, TaxRight KMS keys, and TaxRight service accounts are not configured in this repository.

## Security findings to resolve before staging

1. Firestore delete protection is disabled.
2. The existing bucket combines unrelated operational data; TaxRight needs environment-separated quarantine, clean-document, and export buckets.
3. No checked-in Firestore Security Rules currently protect the proposed TaxRight collections.
4. No TaxRight Firebase Authentication configuration or server-side session flow exists.
5. No malware scanner or Document AI processor is configured.
6. No PAN HMAC pepper/KMS envelope-encryption key is provisioned.
7. No TaxRight BigQuery policy tags, row policies, or authorised views exist.
8. No deployment pipeline currently performs frontend security checks or E2E tests.

## Phase 2 — Architecture and governance

- Define domain model, API contracts, state machine, trust boundaries, and environment boundaries.
- Produce architecture, data dictionary, threat model, tax-rule governance, and deployment runbook.
- Add reproducible BigQuery DDL and Terraform without applying it.

## Phase 3 — Application foundation

- Bootstrap isolated Next.js 16 App Router application in `ITR_APP`.
- Add strict TypeScript, Tailwind 4, accessible primitives, Zod, React Hook Form, Lucide, Sonner, and Vitest.
- Establish server-only configuration, structured redacted logging, typed errors, CSRF/origin checks, and security headers.
- Implement Firebase Admin token verification adapters that fail closed when unconfigured.

## Phase 4 — Client onboarding

- Build responsive six-step flow and dashboard.
- Implement PAN validation/normalisation, server-only HMAC fingerprinting, UUIDv7 identifiers, consent separation, and masked review display.
- Provide Firestore repository interfaces and in-memory development adapters; production endpoints must fail closed without Firebase/GCP configuration.

## Phase 5 — Document platform

- Implement upload signing contract, MIME/extension/signature validation, secure object naming, processing state model, and idempotency keys.
- Add worker service boundary and Document AI/Vertex provider contracts.
- Preserve original objects and create renamed clean copies only after validation.
- Implement export ZIP job contract and short-lived signed-download response.

## Phase 6 — Tax engine

- Implement versioned AY 2026-27 rules metadata and deterministic integer-rupee/paise calculations.
- Cover old/new comparison, 80C group cap, 80D age-dependent limits, 80CCD(1B), 80TTA/80TTB, and 80G category/qualifying-limit logic.
- Mark rules requiring professional verification; official validation material overrides code assumptions.

## Phase 7 — Deductions, 80G, and preference

- Add evidence-linked deduction states and reviewer workflow.
- Keep 80G planning structurally separate from actual evidence.
- Keep Grocery/Services/Gold preference structurally separate from donations and require explicit confirmation.

## Phase 8 — Staff review

- Add role-gated staff dashboard and three-pane case review workspace.
- Require line-item approval and immutable audit events for amendments.
- Never expose raw PAN in list views.

## Phase 9 — Infrastructure definitions

- Add Firestore rules/indexes, BigQuery migrations, Terraform modules, Cloud Run containers, worker container, and Cloud Build staging pipeline.
- Run format/validate/plan only when Terraform is available and credentials/config are supplied.

## Phase 10 — Verification

- Unit: identity, money, tax rules, 80G, naming, consent, roles, state transitions.
- Integration: repositories, upload signing contract, processing idempotency, BigQuery event mapping.
- E2E: synthetic client and staff journey.
- Security: cross-client access, role escalation, spoofed files, traversal, redaction, protected routes.
- Required gates: lint, typecheck, tests, build, dependency audit, `git diff --check`, and secret scan.

## Manual prerequisites before staging

- Create/configure Firebase web app and authentication providers.
- Decide India-compatible Document AI location/processors and validate data-residency requirements.
- Approve Terraform plan for TaxRight-specific buckets, identities, KMS, Secret Manager, BigQuery, Eventarc, Artifact Registry, and Cloud Run.
- Supply approved privacy notice, terms, retention schedule, tax-rule sign-off, and reviewer operating procedure.
- Provision synthetic-only staging fixtures; never copy production taxpayer documents into development.
