# Backend GCP Resources

Provisioned in project `aidirac-503309` on 2026-07-24:

```text
Firestore: projects/aidirac-503309/databases/(default)
Location:  asia-south1
Edition:   Standard, Native mode

Bucket:    gs://aidirac-503309-income-tax-prod
Location:  asia-south1
Class:     Standard

Identity:  income-tax-api@aidirac-503309.iam.gserviceaccount.com
```

Bucket controls:

- Uniform bucket-level access is enabled.
- Public access prevention is enforced.
- Object versioning is enabled.
- Soft delete retention is seven days.

Service-account roles:

- `roles/datastore.user` on project `aidirac-503309`
- `roles/storage.objectAdmin` on the income-tax bucket only
- `roles/bigquery.dataEditor` on project `aidirac-503309`
- `roles/bigquery.jobUser` on project `aidirac-503309`

BigQuery operational index (provisioned 2026-07-28):

```text
Dataset: aidirac-503309.income_tax_ops
Location: asia-south1

Tables:
  clients
  documents
  notices
  responses
  calculations
  reports
```

BigQuery stores searchable workflow metadata and GCS object pointers. Raw
taxpayer PDFs and full response payloads remain in the private, versioned GCS
workspace under:

```text
assessment-years/{AY}/customers/{customer_id}/
```

Every newly onboarded client receives manifests for:

```text
01_source/originals/
02_extracted/renamed/
06_notices/
07_reports/
```

No service-account key file was created. Cloud Run should use the attached
service account when deployment is added.

The API is not deployed. Google ID-token authentication and Firestore RBAC are
implemented, but production startup requires a Google OAuth web client ID.
Firestore delete protection is currently disabled during initial development.
