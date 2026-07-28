from __future__ import annotations

import json
from typing import Protocol

from google.api_core.exceptions import AlreadyExists, PreconditionFailed
from google.cloud import firestore, storage

from itr_backend.filing_models import EligibilityAnswers
from itr_backend.models import CustomerRecord


class CustomerAlreadyExistsError(Exception):
    """Raised when a generated customer ID has already been reserved."""


class CustomerRepository(Protocol):
    def reserve(self, customer: CustomerRecord) -> None: ...

    def set_status(
        self, assessment_year: str, customer_id: str, status: str
    ) -> None: ...

    def get(self, assessment_year: str, customer_id: str) -> CustomerRecord | None: ...

    def list(self, assessment_year: str) -> list[CustomerRecord]: ...

    def set_active(
        self, assessment_year: str, customer_id: str, is_active: bool
    ) -> None: ...


class WorkspaceRepository(Protocol):
    def initialize(self, customer: CustomerRecord) -> None: ...

    def delete(self, workspace_prefix: str) -> None: ...


class FirestoreCustomerRepository:
    """Stores a global customer identity and an AY-specific workspace atomically."""

    def __init__(self, client: firestore.Client):
        self._client = client

    def _global_ref(self, customer_id: str):
        return self._client.collection("customers").document(customer_id)

    def _workspace_ref(self, assessment_year: str, customer_id: str):
        return (
            self._client.collection("assessment_years")
            .document(assessment_year)
            .collection("customers")
            .document(customer_id)
        )

    def reserve(self, customer: CustomerRecord) -> None:
        global_data = {
            "customer_id": customer.customer_id,
            "display_name": customer.display_name,
            "created_at": customer.created_at,
            "updated_at": customer.updated_at,
            "is_active": customer.is_active,
        }
        workspace_data = customer.model_dump(mode="python")
        batch = self._client.batch()
        batch.create(self._global_ref(customer.customer_id), global_data)
        batch.create(
            self._workspace_ref(customer.assessment_year, customer.customer_id),
            workspace_data,
        )
        try:
            batch.commit()
        except AlreadyExists as exc:
            raise CustomerAlreadyExistsError(customer.customer_id) from exc

    def set_status(self, assessment_year: str, customer_id: str, status: str) -> None:
        updates = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        batch = self._client.batch()
        batch.update(self._workspace_ref(assessment_year, customer_id), updates)
        batch.update(
            self._global_ref(customer_id),
            {"updated_at": firestore.SERVER_TIMESTAMP},
        )
        batch.commit()

    def get(self, assessment_year: str, customer_id: str) -> CustomerRecord | None:
        snapshot = self._workspace_ref(assessment_year, customer_id).get()
        if not snapshot.exists:
            return None
        return CustomerRecord.model_validate(snapshot.to_dict())

    def list(self, assessment_year: str) -> list[CustomerRecord]:
        query = (
            self._client.collection("assessment_years")
            .document(assessment_year)
            .collection("customers")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
        )
        return [
            CustomerRecord.model_validate(snapshot.to_dict())
            for snapshot in query.stream()
        ]

    def set_active(
        self, assessment_year: str, customer_id: str, is_active: bool
    ) -> None:
        batch = self._client.batch()
        batch.update(
            self._workspace_ref(assessment_year, customer_id),
            {"is_active": is_active, "updated_at": firestore.SERVER_TIMESTAMP},
        )
        batch.update(
            self._global_ref(customer_id),
            {"is_active": is_active, "updated_at": firestore.SERVER_TIMESTAMP},
        )
        batch.commit()


class GCSWorkspaceRepository:
    def __init__(self, bucket: storage.Bucket):
        self._bucket = bucket

    def _write_json(self, object_name: str, value: dict) -> None:
        blob = self._bucket.blob(object_name)
        try:
            blob.upload_from_string(
                json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                content_type="application/json",
                if_generation_match=0,
            )
        except PreconditionFailed as exc:
            raise CustomerAlreadyExistsError(object_name) from exc

    def initialize(self, customer: CustomerRecord) -> None:
        prefix = customer.workspace_prefix
        customer_json = customer.model_dump(mode="json")
        self._write_json(f"{prefix}customer.json", customer_json)
        self._write_json(
            f"{prefix}client_config.json",
            {
                "client_id": customer.customer_id,
                "assessment_year": customer.assessment_year.removeprefix("AY_"),
                "preferred_regime": customer.preferred_regime,
                "is_active": customer.is_active,
                "password_env_vars": [],
                "preparer_review_required": True,
                "portal_submission_mode": "manual_after_validation",
            },
        )
        self._write_json(
            f"{prefix}02_extracted/client_profile.json",
            {
                "taxpayer": {
                    "pan": None,
                    "date_of_birth": None,
                    "first_name": None,
                    "middle_name": None,
                    "surname": None,
                    "father_name": None,
                    "address": None,
                    "mobile": None,
                    "email": None,
                    "bank_accounts": None,
                    "verification_place": None,
                },
                "eligibility": {key: None for key in EligibilityAnswers.model_fields},
            },
        )
        self._write_json(
            f"{prefix}02_extracted/donations_80g.json",
            {"donations": []},
        )
        self._write_json(
            f"{prefix}03_workpapers/filing_readiness.json",
            {"upload_ready": False, "blockers": ["Customer setup is incomplete."]},
        )
        for folder in (
            "01_source/originals",
            "02_extracted/renamed",
            "06_notices",
            "07_reports",
        ):
            self._write_json(
                f"{prefix}{folder}/manifest.json",
                {
                    "customer_id": customer.customer_id,
                    "assessment_year": customer.assessment_year,
                    "folder": folder,
                    "created_at": customer.created_at.isoformat(),
                },
            )

    def delete(self, workspace_prefix: str) -> None:
        for blob in self._bucket.list_blobs(prefix=workspace_prefix):
            blob.delete()
