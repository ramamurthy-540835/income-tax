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
from itr_backend.analytics import AnalyticsRepository, NoopAnalyticsRepository
from itr_backend.automated_tax import (
    GeminiTaxDocumentExtractor,
    TaxDocumentExtractor,
    reconcile,
)
from itr_backend.document_intake import classify_document
from itr_backend.filing_models import (
    CalculationResult,
    AutomatedTaxCalculation,
    DeductionDetails,
    FilingEvidence,
    FilingProfile,
    NormalizedReturnData,
    IncomeDetails,
    TaxPaidDetails,
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
from itr_backend.pdf_security import PdfPasswordError, unlock_ais_pdf
from itr_backend.storage_models import (
    DocumentRecord,
    FilingState,
    StoredArtifact,
)
from itr_backend.tax_report import calculation_pdf
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
        analytics: AnalyticsRepository | None = None,
        tax_extractor: TaxDocumentExtractor | None = None,
    ):
        self._metadata = metadata
        self._artifacts = artifacts
        self._audit = audit or NoopAuditRepository()
        self._analytics = analytics or NoopAnalyticsRepository()
        self._tax_extractor = tax_extractor

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
        self._analytics.record(
            "calculations",
            {
                "customer_id": customer_id,
                "assessment_year": state.assessment_year,
                "regime": regime,
                "total_income": result.total_income,
                "total_tax": result.total_tax,
                "taxes_paid": result.taxes_paid,
                "balance_payable": result.balance_payable,
                "refund": result.refund,
                "event_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return result

    def generate_calculation_pdf(
        self,
        assessment_year: str,
        customer_id: str,
        regime: str,
        actor: str = "system",
    ) -> tuple[bytes, str]:
        result = self.calculate(assessment_year, customer_id, regime, actor)
        profile, _ = self.get_profile(assessment_year, customer_id)
        automated = None
        if regime == "old":
            try:
                value, _ = self._artifacts.read_json(
                    _prefix(result.assessment_year, customer_id)
                    + "03_workpapers/automated_tax_calculation.json"
                )
                automated = AutomatedTaxCalculation.model_validate(value)
            except ArtifactNotFoundError:
                pass
        payload = calculation_pdf(profile, result, customer_id, automated)
        filename = (
            f"{customer_id}_{result.assessment_year}_{regime.upper()}_Regime_"
            "Tax_and_80G_Workpaper.pdf"
        )
        object_name = (
            _prefix(result.assessment_year, customer_id)
            + f"07_reports/{uuid.uuid4().hex}_{filename}"
        )
        artifact = self._artifacts.write_bytes(
            object_name, payload, "application/pdf"
        )
        self._record(
            result.assessment_year,
            customer_id,
            "calculation.pdf_generated",
            actor,
            {
                "regime": regime,
                "generation": artifact.generation,
                "object_name": object_name,
                "size_bytes": artifact.size_bytes,
            },
        )
        self._analytics.record(
            "reports",
            {
                "customer_id": customer_id,
                "assessment_year": result.assessment_year,
                "regime": regime,
                "report_type": "tax_and_80g_workpaper",
                "object_name": object_name,
                "generation": artifact.generation,
                "event_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return payload, filename

    def extract_and_calculate(
        self,
        assessment_year: str,
        customer_id: str,
        compare_new: bool = False,
        actor: str = "system",
    ) -> AutomatedTaxCalculation:
        state = self.ensure_state(assessment_year, customer_id)
        profile, _ = self.get_profile(state.assessment_year, customer_id)
        extractor = self._tax_extractor or GeminiTaxDocumentExtractor()
        facts = []
        extraction_warnings: list[str] = []
        eligible_categories = {
            "ais", "form16", "26as", "tis", "bank",
            "deduction_80c", "deduction_80d", "deduction_80g", "other",
        }
        for document in self.list_documents(state.assessment_year, customer_id):
            if document.category not in eligible_categories:
                continue
            object_name = document.processing_object_name or document.object_name
            try:
                payload, mime_type, _ = self._artifacts.read_bytes(object_name)
                facts.append(extractor.extract(document.document_id, payload, mime_type))
            except Exception as exc:
                extraction_warnings.append(
                    f"{document.renamed_filename or document.original_filename}: "
                    f"extraction failed ({type(exc).__name__})"
                )
        if not facts:
            raise FilingValidationError(
                "no uploaded tax document could be extracted; review document "
                "classification and backend Gemini configuration"
            )
        reconciled = reconcile(facts)
        reconciled.warnings.extend(extraction_warnings)
        age_band = "below_60"
        if profile.taxpayer.date_of_birth:
            fy_end = datetime(2026, 3, 31).date()
            age = (
                fy_end.year
                - profile.taxpayer.date_of_birth.year
                - (
                    (fy_end.month, fy_end.day)
                    < (
                        profile.taxpayer.date_of_birth.month,
                        profile.taxpayer.date_of_birth.day,
                    )
                )
            )
            age_band = "super_senior" if age >= 80 else "senior" if age >= 60 else "below_60"
        data = NormalizedReturnData(
            assessment_year=state.assessment_year,
            age_band=age_band,
            income=IncomeDetails(
                gross_salary=reconciled.gross_salary,
                exempt_salary_allowances=reconciled.exempt_salary_allowances,
                professional_tax=reconciled.professional_tax,
                savings_interest=reconciled.savings_interest,
                deposit_interest=reconciled.deposit_interest,
                dividend_income=reconciled.dividend_income,
            ),
            deductions=DeductionDetails(
                section_80c_80ccc_80ccd1=reconciled.section_80c,
                section_80d=reconciled.section_80d,
                section_80tta=reconciled.section_80tta,
            ),
            tax_paid=TaxPaidDetails(
                tds_salary=reconciled.tds_salary,
                tds_other=reconciled.tds_other,
            ),
        )
        self.put_return_data(
            state.assessment_year,
            customer_id,
            data,
            state.return_data_generation,
            actor,
        )
        policy = get_tax_year(state.assessment_year)
        old_before = policy.calculate(data, "old")
        plan = old_before.donation_planning
        maximum_donation = (
            plan.max_donation_50_percent_limited if plan else 0
        )
        eligible_80g = plan.max_deduction_50_percent_limited if plan else 0
        after_data = data.model_copy(
            update={
                "deductions": data.deductions.model_copy(
                    update={"section_80g": eligible_80g}
                )
            }
        )
        old_after = policy.calculate(after_data, "old")
        new_result = policy.calculate(data, "new") if compare_new else None
        result = AutomatedTaxCalculation(
            reconciled=reconciled,
            old_before_donation=old_before,
            maximum_useful_donation_50_percent_limited=maximum_donation,
            eligible_80g_deduction=eligible_80g,
            old_after_donation=old_after,
            tax_reduction_from_donation=max(
                old_before.total_tax - old_after.total_tax, 0
            ),
            new_regime=new_result,
            extracted_documents=facts,
        )
        object_name = (
            _prefix(state.assessment_year, customer_id)
            + "03_workpapers/automated_tax_calculation.json"
        )
        try:
            _, generation = self._artifacts.read_json(object_name)
        except ArtifactNotFoundError:
            generation = None
        self._artifacts.write_json(
            object_name, result.model_dump(mode="json"), generation
        )
        self._record(
            state.assessment_year,
            customer_id,
            "calculation.automated_from_documents",
            actor,
            {
                "document_count": len(facts),
                "warning_count": len(reconciled.warnings),
                "compare_new": compare_new,
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
        processing_content = content
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted:
                if category != "ais":
                    raise FilingValidationError(
                        "encrypted PDFs are accepted only for AIS; unlock other PDFs before upload"
                    )
                profile, _ = self.get_profile(state.assessment_year, customer_id)
                if not profile.taxpayer.pan or not profile.taxpayer.date_of_birth:
                    raise FilingValidationError(
                        "PAN and date of birth are required in the client profile "
                        "to unlock an AIS PDF"
                    )
                try:
                    processing_content, page_count = unlock_ais_pdf(
                        content,
                        profile.taxpayer.pan,
                        profile.taxpayer.date_of_birth,
                    )
                except PdfPasswordError as exc:
                    raise FilingValidationError(str(exc)) from exc
            else:
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
        processing_object_name = None
        if processing_content != content:
            processing_object_name = (
                _prefix(state.assessment_year, customer_id)
                + f"02_extracted/unlocked/{document_id}.pdf"
            )
            self._artifacts.write_bytes(
                processing_object_name, processing_content, "application/pdf"
            )
        document = DocumentRecord(
            document_id=document_id,
            customer_id=customer_id,
            assessment_year=state.assessment_year,
            category=category,
            original_filename=original_filename[:255],
            object_name=object_name,
            processing_object_name=processing_object_name,
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

    def auto_upload_document(
        self,
        assessment_year: str,
        customer_id: str,
        original_filename: str,
        content: bytes,
        content_type: str,
        uploaded_by: str,
    ) -> DocumentRecord:
        state = self.ensure_state(assessment_year, customer_id)
        if not content or len(content) > MAX_PDF_SIZE:
            raise FilingValidationError("document must be between 1 byte and 20 MiB")
        extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
        is_pdf = content.startswith(b"%PDF-") and extension == "pdf"
        is_jpeg = content.startswith(b"\xff\xd8\xff") and extension in {"jpg", "jpeg"}
        is_png = content.startswith(b"\x89PNG\r\n\x1a\n") and extension == "png"
        if not (is_pdf or is_jpeg or is_png):
            raise FilingValidationError(
                "only valid PDF, JPG, JPEG, and PNG documents are accepted"
            )
        if any(
            marker in content for marker in (b"/JavaScript", b"/EmbeddedFile", b"/Launch")
        ):
            raise FilingValidationError("document contains active or embedded content")

        profile, _ = self.get_profile(state.assessment_year, customer_id)
        processing_content = content
        page_count = 1
        if is_pdf:
            try:
                reader = PdfReader(io.BytesIO(content), strict=True)
                if reader.is_encrypted:
                    if not profile.taxpayer.pan or not profile.taxpayer.date_of_birth:
                        raise FilingValidationError(
                            "PAN and date of birth are required to unlock an encrypted AIS"
                        )
                    processing_content, page_count = unlock_ais_pdf(
                        content, profile.taxpayer.pan, profile.taxpayer.date_of_birth
                    )
                else:
                    page_count = len(reader.pages)
            except FilingValidationError:
                raise
            except PdfPasswordError as exc:
                raise FilingValidationError(str(exc)) from exc
            except Exception as exc:
                raise FilingValidationError("PDF is malformed or unreadable") from exc
            if page_count < 1 or page_count > 500:
                raise FilingValidationError("PDF page count must be between 1 and 500")

        names = [
            value
            for value in (profile.taxpayer.first_name, profile.taxpayer.surname)
            if value
        ]
        client_label = "_".join(names) or customer_id
        mime_type = (
            "application/pdf" if is_pdf else "image/png" if is_png else "image/jpeg"
        )
        classification = classify_document(
            processing_content, original_filename, client_label, mime_type
        )
        document_id = f"doc_{uuid.uuid4().hex}"
        suffix = ".pdf" if is_pdf else ".png" if is_png else ".jpg"
        original_object = (
            _prefix(state.assessment_year, customer_id)
            + f"01_source/originals/{document_id}{suffix}"
        )
        original_artifact = self._artifacts.write_bytes(
            original_object, content, content_type=mime_type
        )
        renamed_object = (
            _prefix(state.assessment_year, customer_id)
            + f"02_extracted/renamed/{document_id}_{classification.renamed_filename}"
        )
        self._artifacts.write_bytes(
            renamed_object, processing_content, content_type=mime_type
        )
        document = DocumentRecord(
            document_id=document_id,
            customer_id=customer_id,
            assessment_year=state.assessment_year,
            category=classification.category,
            original_filename=original_filename[:255],
            renamed_filename=classification.renamed_filename,
            detected_document_type=classification.document_type,
            classification_confidence=classification.confidence,
            object_name=original_object,
            processing_object_name=renamed_object,
            generation=original_artifact.generation,
            sha256=original_artifact.sha256,
            size_bytes=original_artifact.size_bytes,
            page_count=page_count,
            status=(
                "classified"
                if classification.confidence >= 0.65
                else "review_required"
            ),
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
            "document.auto_classified",
            uploaded_by,
            {
                "document_id": document_id,
                "category": classification.category,
                "renamed_filename": classification.renamed_filename,
                "confidence": classification.confidence,
                "sha256": original_artifact.sha256,
            },
        )
        self._analytics.record(
            "documents",
            {
                "document_id": document_id,
                "customer_id": customer_id,
                "assessment_year": state.assessment_year,
                "category": classification.category,
                "original_filename": original_filename[:255],
                "renamed_filename": classification.renamed_filename,
                "original_object": original_object,
                "renamed_object": renamed_object,
                "sha256": original_artifact.sha256,
                "status": document.status,
                "event_at": document.uploaded_at.isoformat(),
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
