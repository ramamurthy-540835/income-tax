# TaxRight AI

## Document Intelligence Agent

`services/document-agent` is an independent Cloud Run service. It validates and scans
quarantine objects, detects duplicates, performs deterministic-first classification
and Document AI OCR, records provenance, maps candidate evidence, creates PAN-free
standard filenames, preserves originals, promotes clean copies, normalizes AIS data,
reconciles evidence, routes exceptions, and builds server-side ZIP exports.

Run locally with `npm ci`, `npm run typecheck`, and `npm test` from that directory.
Production activation requires an approved Document AI processor, malware backend,
private Eventarc invocation, least-privilege identity, and reviewed Terraform plan.
Encrypted AIS fails closed until an authoritative password convention is verified.

Digitally generated PDFs are read with pinned `pdfplumber` 0.11.10 inside the service
container. Documents with insufficient embedded text fall back to Document AI OCR.
The browser never runs PDF extraction or controls the final filename.

AI-assisted tax intelligence with human review for Indian income-tax return preparation. The application is designed to find every lawfully available, evidence-supported tax benefit while retaining deterministic calculation traces and immutable provenance.

## Current implementation

- Next.js 16 App Router, React 19, strict TypeScript and Tailwind CSS 4.
- Responsive six-step client flow, dashboard, privacy settings, staff queue and evidence-review workspace.
- PAN normalisation/masking/HMAC fingerprint utilities and UUIDv7 identifiers.
- Server-side Firebase ID-token verification and server-controlled roles.
- Deterministic AY 2026-27 calculation engine with old/new comparison, deduction traces and 80G planning controls.
- File metadata, size and magic-byte validation; safe renamed-document convention.
- Deny-by-default Firestore rules, BigQuery DDL and unapplied Terraform infrastructure definitions.
- Unit/security tests and Playwright smoke tests using synthetic data only.

Cloud endpoints intentionally fail closed until approved Firebase/GCP resources are configured. No infrastructure has been deployed or changed.

## Architecture

See [architecture](docs/architecture.md), [data dictionary](docs/data-dictionary.md), [threat model](docs/threat-model.md), and the continuously maintained [implementation plan](docs/IMPLEMENTATION_PLAN.md).

## Local setup

```powershell
cd C:\Users\Personal\income-tax\ITR_APP
Copy-Item .env.example .env.local
npm.cmd install
npm.cmd run dev
```

Use placeholder/local values only. Never place production service-account keys or taxpayer data in local environment files.

## Commands

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test
npm.cmd run build
npm.cmd run security:secrets
npm.cmd run test:e2e
```

Run the production build before Playwright. Browser binaries must be installed separately with `npx playwright install chromium webkit`.

## Firebase setup

1. Create separate Firebase projects/configuration for dev, staging and production or formally map them to isolated GCP projects.
2. Configure email-link/mobile providers intentionally and restrict authorised domains.
3. Configure staff Google sign-in and set custom claims only from an audited admin process.
4. Enable App Check for supported web flows.
5. Run Firestore/Auth emulators locally with `firebase emulators:start`.
6. Deploy `firestore.rules` and indexes only after emulator tests and explicit environment confirmation.

Every protected route verifies a Firebase ID token server-side. A UID or role sent in a request body is never trusted.

## GCP setup

Required APIs include Cloud Run, Artifact Registry, Cloud Build, Firestore, Cloud Storage, Eventarc, Pub/Sub, Document AI, Vertex AI, BigQuery, Secret Manager, Cloud KMS, IAM Credentials and Cloud Logging/Monitoring.

Environment-specific private buckets separate quarantine, clean documents and temporary exports. Existing income-tax storage is a read-only reference and is not a TaxRight upload target.

## Document AI and Vertex AI

- Create Enterprise Document OCR and Form Parser processors only after regional/data-residency review.
- Configure processor IDs and locations through environment variables.
- Keep model IDs configurable.
- Send minimum case-scoped data, label document text as untrusted, require strict JSON schemas and never let model output approve a deduction.

## BigQuery migrations

SQL files in `infra/bigquery` are ordered and replace `${PROJECT_ID}` and `${DATASET}` through a controlled migration runner. BigQuery is downstream analytics/team processing—not application state. Apply policy tags, row policies and authorised group views after identities are approved.

## Infrastructure and deployment

Terraform in `infra/terraform` defines private buckets, service accounts, Secret Manager, KMS and BigQuery without applying them. Before any apply:

```powershell
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform plan -var project_id=... -var environment=staging -out=terraform.tfplan
```

Review the plan. Production requires explicit approval. The root Dockerfile produces a non-root standalone Next.js container. `cloudbuild.yaml` builds an image but deliberately omits automatic deployment.

## Security and privacy model

- Raw PAN is never used in URLs, document IDs, storage paths, Firebase UID or ordinary logs.
- Original evidence is immutable; clean renamed copies link to checksum and object generation.
- Browser access uses authentication and short-lived signed URLs; buckets remain private.
- Consent types are versioned and separate: required tax processing, optional marketing, optional insurance contact, and independent preference confirmation.
- Logs use identifiers and status/error fields only; nested sensitive keys are redacted.
- Uploaded PDFs, OCR text and AI output are untrusted.

## Backup and recovery

Enable Firestore scheduled backups/PITR after an approved RPO/RTO decision. Keep object versioning on clean evidence, a short quarantine lifecycle, and one-day export lifecycle. Test recovery in staging; never infer that versioning alone is a complete backup strategy.

## Tax-rule updates

1. Obtain official Income Tax Department/CBDT validation material.
2. Record authority, source, effective date and verification date in a new immutable rule version.
3. Obtain tax-professional sign-off.
4. Add fixtures for all changed limits/interactions.
5. Preserve historical calculation snapshots against their original rules version.
6. Deploy through staging and compare known official examples before production promotion.

## Known manual prerequisites

Firebase configuration, processor selection, malware scanning, Secret Manager pepper, KMS permissions, policy tags/RLS, approved legal notices, retention policy, tax-professional AY sign-off and staging deployment approval remain mandatory.
