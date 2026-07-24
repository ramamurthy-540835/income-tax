from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from google.api_core.exceptions import Conflict, NotFound
from google.cloud import firestore
from pydantic import BaseModel

from itr_backend.filing_models import FilingProfile
from itr_backend.filing_repositories import (
    ArtifactRepository,
    FilingMetadataRepository,
)
from itr_backend.models import CustomerRecord, normalize_assessment_year
from itr_backend.repositories import GCSWorkspaceRepository
from itr_backend.storage_models import FilingState
from itr_backend.tax_years import get_tax_year


class EnrollmentRequest(BaseModel):
    preferred_regime: Literal["old", "new", "compare"] = "compare"
    copy_profile_from_assessment_year: str | None = None


class EnrollmentError(Exception):
    pass


class FirestoreAssessmentYearEnrollmentRepository:
    def __init__(self, client: firestore.Client):
        self._client = client

    def create_workspace(
        self,
        assessment_year: str,
        customer_id: str,
        preferred_regime: str,
    ) -> CustomerRecord:
        global_ref = self._client.collection("customers").document(customer_id)
        global_snapshot = global_ref.get()
        if not global_snapshot.exists:
            raise EnrollmentError("global customer does not exist")
        global_customer = global_snapshot.to_dict()
        now = datetime.now(timezone.utc)
        record = CustomerRecord(
            customer_id=customer_id,
            assessment_year=assessment_year,
            display_name=global_customer["display_name"],
            preferred_regime=preferred_regime,
            status="provisioning",
            workspace_prefix=(
                f"assessment-years/{assessment_year}/customers/{customer_id}/"
            ),
            created_at=now,
            updated_at=now,
        )
        workspace_ref = (
            self._client.collection("assessment_years")
            .document(assessment_year)
            .collection("customers")
            .document(customer_id)
        )
        try:
            workspace_ref.create(record.model_dump(mode="python"))
        except Conflict as exc:
            raise EnrollmentError(
                "customer is already enrolled in this assessment year"
            ) from exc
        return record

    def set_status(self, assessment_year: str, customer_id: str, status: str) -> None:
        reference = (
            self._client.collection("assessment_years")
            .document(assessment_year)
            .collection("customers")
            .document(customer_id)
        )
        try:
            reference.update(
                {"status": status, "updated_at": firestore.SERVER_TIMESTAMP}
            )
        except NotFound as exc:
            raise EnrollmentError("assessment-year workspace not found") from exc


class AssessmentYearEnrollmentService:
    def __init__(
        self,
        enrollment: FirestoreAssessmentYearEnrollmentRepository,
        workspace: GCSWorkspaceRepository,
        metadata: FilingMetadataRepository,
        artifacts: ArtifactRepository,
    ):
        self._enrollment = enrollment
        self._workspace = workspace
        self._metadata = metadata
        self._artifacts = artifacts

    def enroll(
        self,
        assessment_year: str,
        customer_id: str,
        request: EnrollmentRequest,
    ) -> CustomerRecord:
        ay = normalize_assessment_year(assessment_year)
        get_tax_year(ay)
        record = self._enrollment.create_workspace(
            ay, customer_id, request.preferred_regime
        )
        try:
            self._workspace.initialize(record)
            now = datetime.now(timezone.utc)
            self._metadata.create_state(
                FilingState(
                    customer_id=customer_id,
                    assessment_year=ay,
                    created_at=now,
                    updated_at=now,
                )
            )
            if request.copy_profile_from_assessment_year:
                source_ay = normalize_assessment_year(
                    request.copy_profile_from_assessment_year
                )
                source_name = (
                    f"assessment-years/{source_ay}/customers/{customer_id}/"
                    "02_extracted/client_profile.json"
                )
                target_name = (
                    f"{record.workspace_prefix}02_extracted/client_profile.json"
                )
                profile_payload, _ = self._artifacts.read_json(source_name)
                profile = FilingProfile.model_validate(profile_payload)
                _, target_generation = self._artifacts.read_json(target_name)
                self._artifacts.write_json(
                    target_name,
                    profile.model_dump(mode="json"),
                    target_generation,
                )
            self._enrollment.set_status(ay, customer_id, "active")
        except Exception as exc:
            try:
                self._workspace.delete(record.workspace_prefix)
                self._enrollment.set_status(ay, customer_id, "provisioning_failed")
            except Exception:
                pass
            if isinstance(exc, EnrollmentError):
                raise
            raise EnrollmentError(
                "assessment-year workspace provisioning failed"
            ) from exc
        return record.model_copy(update={"status": "active"})
