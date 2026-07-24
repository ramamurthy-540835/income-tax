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

No service-account key file was created. Cloud Run should use the attached
service account when deployment is added.

The API is not deployed. Google ID-token authentication and Firestore RBAC are
implemented, but production startup requires a Google OAuth web client ID.
Firestore delete protection is currently disabled during initial development.
