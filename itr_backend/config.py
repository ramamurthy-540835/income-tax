from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gcp_project_id: str
    gcs_bucket_name: str
    bigquery_dataset: str = "income_tax_ops"

    @classmethod
    def from_env(cls) -> "Settings":
        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        missing = [
            name
            for name, value in (
                ("GCP_PROJECT_ID", project_id),
                ("GCS_BUCKET_NAME", bucket_name),
            )
            if not value
        ]
        if missing:
            raise RuntimeError("Missing backend configuration: " + ", ".join(missing))
        return cls(
            gcp_project_id=project_id,
            gcs_bucket_name=bucket_name,
            bigquery_dataset=os.getenv("BIGQUERY_DATASET", "income_tax_ops"),
        )
