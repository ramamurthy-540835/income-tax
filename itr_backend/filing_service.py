from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from pypdf import PdfReader

from itr_backend.audit import (
    AuditRepository,
    NoopAuditRepository,
    new_audit_event,
)
from itr_backend.filing_models import (
    CalculationResult,
    FilingEvidence,
    FilingProfile,
    NormalizedReturnData,
    PortalDraft,
    PortalValidationResult,
    ReviewDecision,
    ValidationIssue,
    WorkspaceSummary,
)
from itr_backend.filing_repositories import (
    ArtifactNotFoundError,
    ArtifactRepository,
    FilingMetadataRepository,
    FilingStateNotFoundError,
)
from itr_backend.models import normalize_assessment_year
from itr_backend.storage_models import (
    DocumentRecord,
    FilingState,
    StoredArtifact,
)
from itr_backend.tax_years import get_tax_year

CUSTOMER_ID_PATTERN = re.compile(r"^cus_[0-9a-f]{32}$")
MAX_PDF_SIZE = 20 * 1024 * 1024


class FilingWorkflowError(Exception):
    pass


class FilingArtifactNotFoundError(FilingWorkflowError):
    pass


class FilingValidationError(FilingWorkflowError):
    def __init__(self, message: str, issues: list[ValidationIssue] | None = None):
        super().__init__(message)
        self.issues = issues or []


def _validate_customer_id(customer_id: str) -> str:
    if not CUSTOMER_ID_PATTERN.fullmatch(customer_id):
        raise ValueError("invalid customer ID")
    return customer_id


def _prefix(assessment_year: str, customer_id: str) -> str:
    ay = normalize_assessment_year(assessment_year)
    _validate_customer_id(customer_id)
    return f"assessment-years/{ay}/customers/{customer_id}/"


class FilingService:
    def __init__(
        self,
        metadata: FilingMetadataRepository,
        artifacts: ArtifactRepository,
        audit: AuditRepository | None = None,
    ):
        self._metadata = metadata
        self._artifacts = artifacts
        self._audit = audit or NoopAuditRepository()

    def _record(
        self,
        assessment_year: str,
        customer_id: str,
        action: str,
        actor: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._audit.append(
            new_audit_event(assessment_year, customer_id, action, actor, details)
        )

    def ensure_state(self, assessment_year: str, customer_id: str) -> FilingState:
        ay = normalize_assessment_year(assessment_year)
        get_tax_year(ay)
        _validate_customer_id(customer_id)
        try:
            return self._metadata.get_state(ay, customer_id)
        except FilingStateNotFoundError:
            if not self._metadata.workspace_exists(ay, customer_id):
                raise FilingValidationError(
                    "customer is not enrolled in this assessment year"
                )
            now = datetime.now(timezone.utc)
            state = FilingState(
                customer_id=customer_id,
                assessment_year=ay,
                status="draft",
                created_at=now,
                updated_at=now,
            )
            self._metadata.create_state(state)
            return state

    def _read_json(self, object_name: str) -> tuple[dict[str, Any], int]:
        try:
            return self._artifacts.read_json(object_name)
        except ArtifactNotFoundError as exc:
            raise FilingArtifactNotFoundError(object_name) from exc

    def get_profile(
        self, assessment_year: str, customer_id: str
    ) -> tuple[FilingProfile, int]:
        object_name = (
            _prefix(assessment_year, customer_id) + "02_extracted/client_profile.json"
        )
        payload, generation = self._read_json(object_name)
        return FilingProfile.model_validate(payload), generation

    def put_profile(
        self,
        assessment_year: str,
        customer_id: str,
        profile: FilingProfile,
        expected_generation: int | None,
        actor: str = "system",
    ) -> StoredArtifact:
        state = self.ensure_state(assessment_year, customer_id)
        object_name = (
            _prefix(state.assessment_year, customer_id)
            + "02_extracted/client_profile.json"
        )
        artifact = self._artifacts.write_json(
            object_name,
            profile.model_dump(mode="json"),
            expected_generation,
        )
        self._metadata.update_state(
            state.assessment_year,
            customer_id,
            {
                "profile_generation": artifact.generation,
                "status": "documents_pending",
                "preparer_approved": False,
            },
        )
        self._record(
            state.assessment_year,
            customer_id,
            "profile.updated",
            actor,
            {"generation": artifact.generation},
        )
        return artifact

    def get_return_data(
        self, assessment_year: str, customer_id: str
    ) -> tuple[NormalizedReturnData, int]:
        object_name = (
            _prefix(assessment_year, customer_id) + "02_extracted/return_data.json"
        )
        payload, generation = self._read_json(object_name)
        return NormalizedReturnData.model_validate(payload), generation

    def put_return_data(
        self,
        assessment_year: str,
        customer_id: str,
        data: NormalizedReturnData,
        expected_generation: int | None,
        actor: str = "system",
    ) -> StoredArtifact:
        state = self.ensure_state(assessment_year, customer_id)
        if normalize_assessment_year(data.assessment_year) != state.assessment_year:
            raise FilingValidationError(
                "return data assessment year does not match the workspace"
            )
        object_name = (
            _prefix(state.assessment_year, customer_id)
            + "02_extracted/return_data.json"
        )
        artifact = self._artifacts.write_json(
            object_name,
            data.model_dump(mode="json"),
            expected_generation,
        )
        self._metadata.update_state(
            state.assessment_year,
            customer_id,
            {
                "return_data_generation": artifact.generation,
                "status": "review_pending",
                "preparer_approved": False,
            },
        )
        self._record(
            state.assessment_year,
            customer_id,
            "return_data.updated",
            actor,
            {"generation": artifact.generation},
        )
        return artifact

    def calculate(
        self,
        assessment_year: str,
        customer_id: str,
        regime: str,
        actor: str = "system",
    ) -> CalculationResult:
        state = self.ensure_state(assessment_year, customer_id)
        profile, _ = self.get_profile(state.assessment_year, customer_id)
        data, _ = self.get_return_data(state.assessment_year, customer_id)
        policy = get_tax_year(state.assessment_year)
        result = policy.calculate(data, regime)
        result.issues = policy.validate_eligibility(profile, data) + result.issues
        object_name = (
            _prefix(state.assessment_year, customer_id)
            + "03_workpapers/tax_calculation.json"
        )
        existing_generation = state.calculation_generation
        artifact = self._artifacts.write_json(
            object_name,
            result.model_dump(mode="json"),
            existing_generation,
        )
        self._metadata.update_state(
            state.assessment_year,
            customer_id,
            {"calculation_generation": artifact.generation},
        )
        self._record(
            state.assessment_year,
            customer_id,
            "calculation.completed",
            actor,
            {
                "generation": artifact.generation,
                "regime": regime,
                "has_blockers": any(
                    issue.severity == "blocker" for issue in result.issues
                ),
            },
        )
        return result

    def upload_document(
        self,
        assessment_year: str,
        customer_id: str,
        category: str,
        original_filename: str,
        content: bytes,
        uploaded_by: str,
    ) -> DocumentRecord:
        state = self.ensure_state(assessment_year, customer_id)
        if len(content) > MAX_PDF_SIZE:
            raise FilingValidationError("PDF exceeds the 20 MiB upload limit")
        if not content.startswith(b"%PDF-"):
            raise FilingValidationError("uploaded document is not a PDF")
        active_markers = (b"/JavaScript", b"/EmbeddedFile", b"/Launch")
        if any(marker in content for marker in active_markers):
            raise FilingValidationError(
                "PDF contains active or embedded content and cannot be accepted"
            )
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise FilingValidationError(
                    "encrypted PDFs must be unlocked before upload"
                )
            page_count = len(reader.pages)
        except FilingValidationError:
            raise
        except Exception as exc:
            raise FilingValidationError("PDF is malformed or unreadable") from exc
        if page_count < 1 or page_count > 500:
            raise FilingValidationError("PDF page count must be between 1 and 500")

        document_id = f"doc_{uuid.uuid4().hex}"
        object_name = (
            _prefix(state.assessment_year, customer_id)
            + f"01_source/{category}/{document_id}.pdf"
        )
        artifact = self._artifacts.write_bytes(object_name, content, "application/pdf")
        document = DocumentRecord(
            document_id=document_id,
            customer_id=customer_id,
            assessment_year=state.assessment_year,
            category=category,
            original_filename=original_filename[:255],
            object_name=object_name,
            generation=artifact.generation,
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            page_count=page_count,
            uploaded_at=datetime.now(timezone.utc),
            uploaded_by=uploaded_by,
        )
        self._metadata.create_document(document)
        self._metadata.update_state(
            state.assessment_year,
            customer_id,
            {"status": "documents_pending", "preparer_approved": False},
        )
        self._record(
            state.assessment_year,
            customer_id,
            "document.uploaded",
            uploaded_by,
            {
                "document_id": document_id,
                "category": category,
                "generation": artifact.generation,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
            },
        )
        return document

    def download_document(
        self, assessment_year: str, customer_id: str, document_id: str
    ) -> tuple[bytes, DocumentRecord]:
        state = self.ensure_state(assessment_year, customer_id)
        for document in self._metadata.list_documents(
            state.assessment_year, customer_id
        ):
            if document.document_id == document_id:
                payload, _, generation = self._artifacts.read_bytes(
                    document.object_name
                )
                if generation != document.generation:
                    raise FilingValidationError(
                        "document generation no longer matches its evidence record"
                    )
                return payload, document
        raise FilingArtifactNotFoundError(document_id)

    def list_documents(
        self, assessment_year: str, customer_id: str
    ) -> list[DocumentRecord]:
        state = self.ensure_state(assessment_year, customer_id)
        return self._metadata.list_documents(state.assessment_year, customer_id)

    def get_portal_draft(
        self, assessment_year: str, customer_id: str
    ) -> tuple[dict[str, Any], int]:
        state = self.ensure_state(assessment_year, customer_id)
        return self._read_json(
            _prefix(state.assessment_year, customer_id)
            + "04_portal_export/portal_draft.json"
        )

    def put_portal_draft(
        self,
        assessment_year: str,
        customer_id: str,
        draft: PortalDraft,
        expected_generation: int | None,
        actor: str = "system",
    ) -> PortalValidationResult:
        state = self.ensure_state(assessment_year, customer_id)
        policy = get_tax_year(state.assessment_year)
        prefix = _prefix(state.assessment_year, customer_id)
        draft_artifact = self._artifacts.write_json(
            prefix + "04_portal_export/portal_draft.json",
            draft.payload,
            expected_generation,
        )
        validation = policy.validate_portal_payload(draft.payload)
        validation_artifact = self._artifacts.write_json(
            prefix + "03_workpapers/portal_schema_validation.json",
            validation.model_dump(mode="json"),
            state.validation_generation,
        )
        self._metadata.update_state(
            state.assessment_year,
            customer_id,
            {
                "portal_draft_generation": draft_artifact.generation,
                "validation_generation": validation_artifact.generation,
                "schema_valid": validation.valid,
                "status": "review_pending",
                "preparer_approved": False,
                "portal_validation_completed": False,
            },
        )
        self._record(
            state.assessment_year,
            customer_id,
            "portal_draft.validated",
            actor,
            {
                "draft_generation": draft_artifact.generation,
                "validation_generation": validation_artifact.generation,
                "schema_valid": validation.valid,
                "issue_count": len(validation.issues),
            },
        )
        return validation

    def get_portal_validation(
        self, assessment_year: str, customer_id: str
    ) -> PortalValidationResult:
        object_name = (
            _prefix(assessment_year, customer_id)
            + "03_workpapers/portal_schema_validation.json"
        )
        payload, _ = self._read_json(object_name)
        return PortalValidationResult.model_validate(payload)

    def review(
        self,
        assessment_year: str,
        customer_id: str,
        decision: ReviewDecision,
        reviewed_by: str,
    ) -> FilingState:
        state = self.ensure_state(assessment_year, customer_id)
        if decision.decision == "approve":
            blockers = self.summary(state.assessment_year, customer_id).blockers
            if blockers:
                raise FilingValidationError(
                    "filing workspace has unresolved blockers", blockers
                )
            if not decision.portal_validation_completed:
                raise FilingValidationError(
                    "official portal/offline-utility validation must be completed"
                )
        payload = {
            **decision.model_dump(mode="json"),
            "reviewed_by": reviewed_by,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        artifact = self._artifacts.write_json(
            _prefix(state.assessment_year, customer_id)
            + "03_workpapers/preparer_review.json",
            payload,
            state.review_generation,
        )
        approved = decision.decision == "approve"
        updated = self._metadata.update_state(
            state.assessment_year,
            customer_id,
            {
                "review_generation": artifact.generation,
                "preparer_approved": approved,
                "portal_validation_completed": (
                    approved and decision.portal_validation_completed
                ),
                "status": "ready_for_portal" if approved else "review_pending",
            },
        )
        self._record(
            state.assessment_year,
            customer_id,
            "review.recorded",
            reviewed_by,
            {
                "decision": decision.decision,
                "review_generation": artifact.generation,
                "portal_validation_completed": (
                    approved and decision.portal_validation_completed
                ),
            },
        )
        return updated

    def export_portal_json(
        self,
        assessment_year: str,
        customer_id: str,
        actor: str = "system",
    ) -> tuple[bytes, str]:
        state = self.ensure_state(assessment_year, customer_id)
        if not (
            state.schema_valid
            and state.preparer_approved
            and state.portal_validation_completed
        ):
            raise FilingValidationError(
                "schema validation, portal validation, and preparer approval "
                "are required before export"
            )
        object_name = (
            _prefix(state.assessment_year, customer_id)
            + "04_portal_export/portal_draft.json"
        )
        payload, _, _ = self._artifacts.read_bytes(object_name)
        self._record(
            state.assessment_year,
            customer_id,
            "portal_json.exported",
            actor,
            {
                "generation": state.portal_draft_generation,
                "size_bytes": len(payload),
            },
        )
        return payload, f"ITR1_{state.assessment_year}_{customer_id}.json"

    def record_filing_evidence(
        self,
        assessment_year: str,
        customer_id: str,
        evidence: FilingEvidence,
        actor: str = "system",
    ) -> FilingState:
        state = self.ensure_state(assessment_year, customer_id)
        if not state.preparer_approved:
            raise FilingValidationError(
                "preparer approval is required before recording filing evidence"
            )
        artifact = self._artifacts.write_json(
            _prefix(state.assessment_year, customer_id)
            + "05_filing_evidence/filing_evidence.json",
            evidence.model_dump(mode="json"),
            state.filing_evidence_generation,
        )
        status = (
            "verified"
            if evidence.verification_status in {"e_verified", "verified"}
            else "filed"
        )
        updated = self._metadata.update_state(
            state.assessment_year,
            customer_id,
            {
                "filing_evidence_generation": artifact.generation,
                "status": status,
            },
        )
        self._record(
            state.assessment_year,
            customer_id,
            "filing_evidence.recorded",
            actor,
            {
                "generation": artifact.generation,
                "verification_status": evidence.verification_status,
                "status": status,
            },
        )
        return updated

    def summary(self, assessment_year: str, customer_id: str) -> WorkspaceSummary:
        state = self.ensure_state(assessment_year, customer_id)
        blockers: list[ValidationIssue] = []
        profile: FilingProfile | None = None
        data: NormalizedReturnData | None = None
        try:
            profile, _ = self.get_profile(state.assessment_year, customer_id)
        except FilingArtifactNotFoundError:
            blockers.append(
                ValidationIssue(
                    code="PROFILE_MISSING",
                    severity="blocker",
                    path="/profile",
                    message="taxpayer profile is missing",
                )
            )
        try:
            data, _ = self.get_return_data(state.assessment_year, customer_id)
        except FilingArtifactNotFoundError:
            blockers.append(
                ValidationIssue(
                    code="RETURN_DATA_MISSING",
                    severity="blocker",
                    path="/return-data",
                    message="normalized return data is missing",
                )
            )
        if profile and data:
            policy = get_tax_year(state.assessment_year)
            blockers.extend(policy.validate_eligibility(profile, data))
            taxpayer = profile.taxpayer
            required_profile = {
                "pan": taxpayer.pan,
                "date_of_birth": taxpayer.date_of_birth,
                "first_name": taxpayer.first_name,
                "surname": taxpayer.surname,
                "father_name": taxpayer.father_name,
                "address": taxpayer.address,
                "mobile": taxpayer.mobile,
                "email": taxpayer.email,
                "verification_place": taxpayer.verification_place,
                "refund_bank_account": any(
                    account.nominated_for_refund for account in taxpayer.bank_accounts
                ),
            }
            for field, value in required_profile.items():
                if not value:
                    blockers.append(
                        ValidationIssue(
                            code="PROFILE_REQUIRED",
                            severity="blocker",
                            path=f"/profile/taxpayer/{field}",
                            message=f"{field} is required",
                        )
                    )
        if not state.calculation_generation:
            blockers.append(
                ValidationIssue(
                    code="CALCULATION_MISSING",
                    severity="blocker",
                    path="/calculation",
                    message="tax calculation workpaper is missing",
                )
            )
        if not state.portal_draft_generation:
            blockers.append(
                ValidationIssue(
                    code="PORTAL_DRAFT_MISSING",
                    severity="blocker",
                    path="/portal-draft",
                    message="official ITR-1 portal JSON draft is missing",
                )
            )
        elif not state.schema_valid:
            blockers.append(
                ValidationIssue(
                    code="PORTAL_SCHEMA_INVALID",
                    severity="blocker",
                    path="/portal-draft",
                    message="portal JSON does not satisfy the official schema",
                )
            )
        return WorkspaceSummary(
            customer_id=customer_id,
            assessment_year=state.assessment_year,
            status=state.status,
            profile_complete=bool(profile)
            and not any(issue.code == "PROFILE_REQUIRED" for issue in blockers),
            normalized_return_present=bool(data),
            portal_draft_present=bool(state.portal_draft_generation),
            schema_valid=state.schema_valid,
            preparer_approved=state.preparer_approved,
            portal_validation_completed=state.portal_validation_completed,
            filing_evidence_present=bool(state.filing_evidence_generation),
            blockers=blockers,
        )
