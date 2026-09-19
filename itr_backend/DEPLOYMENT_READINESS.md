# Production and E-Filing Readiness

## Completed in the backend

- Permanent `cus_<uuid4>` customer identity with isolated AY workspaces
- Firestore metadata, role-based access, and append-only workflow audit events
- Private, versioned GCS evidence and artifact storage
- PDF integrity checks, SHA-256 evidence, and generation-based concurrency
- AY-specific eligibility, advisory calculation, and schema validation policies
- Independent review, official-utility attestation, and export gates
- Filing acknowledgement and verification evidence capture
- Non-root production container and health/OpenAPI endpoints

## Required before production deployment

1. Create a Google OAuth web client for the frontend and configure its exact
   authorized origins. Set `GOOGLE_OAUTH_CLIENT_ID` on Cloud Run.
2. Decide the frontend domain and CORS policy. The backend intentionally does
   not guess trusted browser origins.
3. Enable Cloud Run and the selected image registry, build and push the image,
   deploy it with the existing service account, and restrict ingress/IAM.
4. Enable Firestore delete protection after migration and recovery procedures
   have been exercised.
5. Configure log retention, alerting, backups/exports, privacy retention, and
   incident-response ownership for taxpayer data.
6. Run acceptance cases against the current official offline utility/portal
   and obtain tax-preparer approval before using real filings.

## Required for e-filing

The current system prepares and controls an official portal/offline-utility
JSON. A preparer still submits it through the official portal and records the
acknowledgement and verification evidence.

Direct programmatic submission is a separate integration. It requires an
authorized ERI/API arrangement, department-issued software identity, supported
authentication/signing, consent records, and a dedicated security review.
Passwords, Aadhaar OTPs, EVCs, and portal sessions must not be stored here.

## Next assessment year

The customer identity and optional profile are reusable. Financial figures,
documents, calculations, validation, approvals, and filing evidence remain
isolated by AY.

AY 2027-28 remains disabled until the department publishes the notified form,
schema, validation rules, and utility. Follow `TAX_YEAR_RUNBOOK.md`; do not copy
AY 2026-27 tax rules forward without official artifacts and regression tests.

## Cloud Build deployment

The repository includes `cloudbuild.yaml` at the repository root. It runs both
test suites, builds `itr_backend/Dockerfile`, pushes the image to Artifact
Registry, and deploys the `income-tax-api` Cloud Run service.

Before running the build, create the Artifact Registry repository and runtime
service account, grant the runtime account Firestore and bucket access, and set
a real Google OAuth web-client ID in the Cloud Build trigger or command:

```bash
gcloud artifacts repositories create income-tax \
  --repository-format=docker --location=asia-south1 \
  --project=aidirac-503309

gcloud builds submit . --config=cloudbuild.yaml \
  --substitutions=_GOOGLE_OAUTH_CLIENT_ID=YOUR_WEB_CLIENT_ID,_TAG=$BUILD_ID \
  --project=aidirac-503309
```

The Cloud Run service is intentionally reachable at the platform edge so the
application can validate Google OAuth bearer tokens itself. Do not remove the
Google authentication requirement or deploy with `AUTH_MODE=development`.
