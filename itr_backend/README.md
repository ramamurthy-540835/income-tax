# Income Tax Filing Backend

FastAPI backend for evidence-linked ITR-1 preparation. Customer identity is
permanent and globally unique. Each assessment year has a separate Firestore
workspace and versioned GCS artifact prefix.

## Implemented workflow

1. Create a customer with a `cus_<uuid4>` identifier.
2. Enroll the same customer in an enabled assessment year.
3. Maintain the taxpayer profile and ITR-1 eligibility answers.
4. Upload validated PDFs. The backend records SHA-256, object generation, size,
   page count, uploader, and original filename.
5. Maintain normalized income, deduction, filing, and tax-paid data.
6. Generate an advisory old/new regime workpaper using the selected AY policy.
7. Import an official prefill/offline-utility ITR-1 JSON.
8. Validate it against the pinned official JSON Schema.
9. Record independent preparer review and official portal/utility validation.
10. Export only after all gates pass.
11. Record acknowledgement and verification evidence after manual filing.
12. Append actor-attributed workflow events to the AY/customer Firestore audit
    collection without copying taxpayer or return payloads into audit metadata.

Portal login, passwords, OTPs, return submission, and e-verification are not
automated. Direct vendor JSON generation also requires the department-issued
software/ERI registration identifier required by `CreationInfo`.

## Assessment-year safety

Tax law is implemented through `itr_backend.tax_years.TaxYearPolicy`. AY
2026-27 pins ITR-1 schema version 1.1 and its release dates. Unsupported years
fail closed. AY 2027-28 cannot be enabled until the official form, schema,
validation rules, and tax policy are published and tested.

The same customer ID can be enrolled in a later enabled AY through:

```text
POST /api/assessment-years/{ay}/customers/{customer_id}/enroll
```

Profile carry-forward is optional and never carries return figures or filing
approval.

## Configuration

```text
GCP_PROJECT_ID=aidirac-503309
GCS_BUCKET_NAME=aidirac-503309-income-tax-prod
ENVIRONMENT=production
AUTH_MODE=google
GOOGLE_OAUTH_CLIENT_ID=<web OAuth client ID>
```

Production startup fails if `GOOGLE_OAUTH_CLIENT_ID` is absent. For local-only
development:

```bash
ENVIRONMENT=development \
AUTH_MODE=development \
GCP_PROJECT_ID=aidirac-503309 \
GCS_BUCKET_NAME=aidirac-503309-income-tax-prod \
.venv/bin/uvicorn itr_backend.app:app --reload
```

Development authentication cannot run when `ENVIRONMENT=production`.

## Authorization

Google ID tokens are verified and mapped to Firestore access records:

```text
users/{google_subject}
user_access_by_email/{verified_email}
```

Roles are `admin`, `preparer`, `reviewer`, and `customer`. Customer-scoped users
can only access customer IDs explicitly assigned to them.

## Concurrency

Mutable JSON artifacts use the GCS generation as an ETag. Read a profile,
return-data, or portal-draft resource, then send its `ETag` value in `If-Match`
when updating it. Stale writes return HTTP 409.

## API documentation

OpenAPI is available at `/api/docs`. Core resources include customers,
enrollment, profile, return data, calculations, documents, portal draft,
schema validation, review, export, filing evidence, and workspace summary.

## Tests

```bash
.venv/bin/python -m unittest discover -s itr_backend/tests -v
.venv/bin/python -m unittest discover -s itr_agent/tests -v
```
