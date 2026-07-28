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
13. Accept encrypted AIS PDFs by deriving the standard password from the saved
    client profile (`lowercase PAN + DOB as DDMMYYYY`). The password is never
    stored and no client-specific `.env` file is used.
14. Create evidence-linked notice/demand cases, generate conservative response
    drafts, and require independent professional review before submission.
15. Save searchable client/document/notice/response/calculation/report metadata
    in BigQuery while keeping raw documents and response bodies in private GCS.
16. Generate separate old/new regime PDF workpapers under each client's
    `07_reports/` prefix; old-regime reports include 80G planning.
17. Extract tax facts directly from uploaded Form 16, AIS, Form 26AS and
    deduction evidence using one backend-level Gemini configuration, reconcile
    duplicate sources, and compute old-regime tax before/after the maximum
    useful 50%-limited 80G donation.

## Notice and demand workflow

Notice cases support outstanding demands and common proceedings including
sections 139(9), 142(1), 143(1)(a), 143(2), 144, 148/148A, 154, 245, 263,
270A, and 277A. Drafts are stored below `06_notices/` in the customer's AY
workspace. They include the portal route, annexure index, missing-information
checks, and risk flags.

The system deliberately does not submit responses to the portal. High-risk
proceedings are flagged, and a section 277A case produces only a protective
preliminary response pending review by a qualified tax professional/advocate.
Official portal responses cannot be edited or withdrawn after submission, so
the backend keeps `submission_ready=false` until the reviewer gate passes.

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

Notice endpoints:

```text
POST /api/assessment-years/{ay}/customers/{id}/notices
GET  /api/assessment-years/{ay}/customers/{id}/notices
POST /api/assessment-years/{ay}/customers/{id}/notices/{case_id}/draft
POST /api/assessment-years/{ay}/customers/{id}/notices/{case_id}/review
```

## Automatic evidence intake

The frontend sends up to 50 PDF/JPG/PNG files to the batch endpoint without
requiring the user to select document types:

```text
POST /api/assessment-years/{ay}/customers/{id}/documents/batch
```

For every accepted file the backend:

1. validates the file signature, size, page count, and active-content markers;
2. unlocks an encrypted AIS from the saved PAN and DOB where applicable;
3. classifies common tax documents and notices;
4. retains the exact immutable upload under `01_source/originals/`;
5. creates a contextual client-prefixed copy under
   `02_extracted/renamed/`;
6. records SHA-256, confidence, category, filenames, generations, and actor.

Low-confidence documents remain in the client workspace with
`review_required` status instead of being assigned an invented category.

Pasted notice text can be analyzed before case creation:

```text
POST /api/assessment-years/{ay}/customers/{id}/notices/analyze
```

The result includes detected section/DIN/deadline/demand, urgency, portal
route, recommended course, evidence checklist, unresolved questions, and
professional-review risk flags.

## Automatic tax calculation from documents

```text
POST /api/assessment-years/{ay}/customers/{id}/automation/calculate
POST /api/assessment-years/{ay}/customers/{id}/automation/calculate?compare_new=true
```

The pipeline reads the renamed processing copies from GCS, extracts annual tax
facts, excludes other financial years, uses source priority to avoid adding AIS
and Form 16 salary twice, persists normalized return data, and returns:

- old-regime tax and balance before donation;
- maximum useful donation for the 50%-deduction limited 80G category;
- eligible 80G deduction;
- old-regime tax and final balance after donation;
- tax reduction achieved;
- optional new-regime comparison;
- source documents and reconciliation warnings.

Configure `GEMINI_API_KEY` once for the backend runtime. Client-specific API
keys or password `.env` files are not read.

## Tests

```bash
.venv/bin/python -m unittest discover -s itr_backend/tests -v
.venv/bin/python -m unittest discover -s itr_agent/tests -v
```
