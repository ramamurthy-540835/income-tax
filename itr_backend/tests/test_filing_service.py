from __future__ import annotations

import hashlib
import io
import json
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from pypdf import PdfWriter

from itr_backend.filing_models import (
    BankAccount,
    EligibilityAnswers,
    ExtractedTaxFacts,
    FilingProfile,
    IncomeDetails,
    NormalizedReturnData,
    ReviewDecision,
    TaxpayerProfile,
)
from itr_backend.filing_repositories import (
    ArtifactNotFoundError,
    ConcurrentUpdateError,
    FilingStateNotFoundError,
)
from itr_backend.filing_service import FilingService, FilingValidationError
from itr_backend.storage_models import (
    DocumentRecord,
    FilingState,
    StoredArtifact,
)

CUSTOMER_ID = "cus_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
AY = "AY_2026-27"
PREFIX = f"assessment-years/{AY}/customers/{CUSTOMER_ID}/"


class InMemoryMetadata:
    def __init__(self):
        self.states: dict[tuple[str, str], FilingState] = {}
        self.documents: list[DocumentRecord] = []
        self.workspaces: set[tuple[str, str]] = {(AY, CUSTOMER_ID)}

    def workspace_exists(self, assessment_year: str, customer_id: str) -> bool:
        return (assessment_year, customer_id) in self.workspaces

    def create_state(self, state: FilingState) -> None:
        key = (state.assessment_year, state.customer_id)
        if key in self.states:
            raise ConcurrentUpdateError("state")
        self.states[key] = state

    def get_state(self, assessment_year: str, customer_id: str) -> FilingState:
        try:
            return self.states[(assessment_year, customer_id)]
        except KeyError as exc:
            raise FilingStateNotFoundError(customer_id) from exc

    def update_state(
        self, assessment_year: str, customer_id: str, updates: dict[str, Any]
    ) -> FilingState:
        key = (assessment_year, customer_id)
        state = self.get_state(*key)
        state = state.model_copy(
            update={**updates, "updated_at": datetime.now(timezone.utc)}
        )
        self.states[key] = state
        return state

    def create_document(self, document: DocumentRecord) -> None:
        self.documents.append(document)

    def list_documents(
        self, assessment_year: str, customer_id: str
    ) -> list[DocumentRecord]:
        return [
            document
            for document in self.documents
            if document.assessment_year == assessment_year
            and document.customer_id == customer_id
        ]


class InMemoryArtifacts:
    def __init__(self):
        self.values: dict[str, tuple[bytes, str, int]] = {}
        self.next_generation = 1

    def _write(
        self,
        name: str,
        payload: bytes,
        content_type: str,
        expected_generation: int | None,
    ) -> StoredArtifact:
        existing = self.values.get(name)
        if existing and expected_generation != existing[2]:
            raise ConcurrentUpdateError(name)
        if not existing and expected_generation is not None:
            raise ConcurrentUpdateError(name)
        generation = self.next_generation
        self.next_generation += 1
        self.values[name] = (payload, content_type, generation)
        return StoredArtifact(
            object_name=name,
            generation=generation,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            content_type=content_type,
            updated_at=datetime.now(timezone.utc),
        )

    def write_json(
        self,
        object_name: str,
        payload: dict[str, Any],
        expected_generation: int | None,
    ) -> StoredArtifact:
        encoded = json.dumps(payload, default=str).encode()
        return self._write(
            object_name, encoded, "application/json", expected_generation
        )

    def read_json(self, object_name: str):
        payload, _, generation = self.read_bytes(object_name)
        return json.loads(payload), generation

    def write_bytes(
        self, object_name: str, payload: bytes, content_type: str
    ) -> StoredArtifact:
        return self._write(object_name, payload, content_type, None)

    def read_bytes(self, object_name: str):
        try:
            return self.values[object_name]
        except KeyError as exc:
            raise ArtifactNotFoundError(object_name) from exc


def complete_profile() -> FilingProfile:
    return FilingProfile(
        taxpayer=TaxpayerProfile(
            pan="ABCDE1234F",
            date_of_birth=date(1990, 1, 1),
            first_name="Example",
            surname="Customer",
            father_name="Example Parent",
            address={"line1": "Address", "pin": "400001"},
            mobile="9999999999",
            email="customer@example.com",
            verification_place="Mumbai",
            bank_accounts=[
                BankAccount(
                    account_number_last4="1234",
                    ifsc="ABCD0123456",
                    bank_name="Example Bank",
                    nominated_for_refund=True,
                )
            ],
        ),
        eligibility=EligibilityAnswers(
            **{field: True for field in EligibilityAnswers.model_fields}
        ),
    )


class FilingServiceTests(unittest.TestCase):
    def setUp(self):
        self.metadata = InMemoryMetadata()
        self.artifacts = InMemoryArtifacts()
        self.service = FilingService(self.metadata, self.artifacts)

    def create_profile_and_return(self):
        profile_artifact = self.service.put_profile(
            AY, CUSTOMER_ID, complete_profile(), None
        )
        data_artifact = self.service.put_return_data(
            AY,
            CUSTOMER_ID,
            NormalizedReturnData(
                assessment_year=AY,
                age_band="below_60",
                income=IncomeDetails(
                    gross_salary=Decimal("1000000"),
                    savings_interest=Decimal("5000"),
                ),
            ),
            None,
        )
        return profile_artifact, data_artifact

    def test_profile_update_requires_current_generation(self):
        artifact, _ = self.create_profile_and_return()

        with self.assertRaises(ConcurrentUpdateError):
            self.service.put_profile(
                AY, CUSTOMER_ID, complete_profile(), artifact.generation + 1
            )

    def test_calculation_is_persisted_and_eligibility_checked(self):
        self.create_profile_and_return()

        result = self.service.calculate(AY, CUSTOMER_ID, "new")

        self.assertEqual(result.assessment_year, AY)
        self.assertTrue(
            any(
                issue.code == "PORTAL_RECOMPUTATION_REQUIRED" for issue in result.issues
            )
        )
        self.assertIn(
            PREFIX + "03_workpapers/tax_calculation.json",
            self.artifacts.values,
        )

    def test_old_regime_pdf_is_generated_and_stored_under_client_id(self):
        self.create_profile_and_return()

        payload, filename = self.service.generate_calculation_pdf(
            AY, CUSTOMER_ID, "old", "reviewer-1"
        )

        self.assertTrue(payload.startswith(b"%PDF-"))
        self.assertIn("OLD_Regime", filename)
        report_objects = [
            name for name in self.artifacts.values if "/07_reports/" in name
        ]
        self.assertEqual(len(report_objects), 1)
        self.assertIn(CUSTOMER_ID, report_objects[0])

    def test_documents_are_reconciled_into_tax_and_maximum_donation(self):
        class FakeExtractor:
            def __init__(self):
                self.calls = 0

            def extract(self, document_id, payload, mime_type):
                self.calls += 1
                if self.calls == 1:
                    return ExtractedTaxFacts(
                        document_id=document_id,
                        document_type="Form 16",
                        issuer="Employer",
                        assessment_year="2026-27",
                        gross_salary=2_000_000,
                        professional_tax=2_500,
                        tds_salary=250_000,
                        section_80c=150_000,
                        evidence_quality="high",
                    )
                return ExtractedTaxFacts(
                    document_id=document_id,
                    document_type="Annual Information Statement",
                    issuer="Income Tax Department",
                    assessment_year="2026-27",
                    gross_salary=2_000_000,
                    savings_interest=15_000,
                    deposit_interest=40_000,
                    tds_salary=250_000,
                    evidence_quality="high",
                )

        self.service = FilingService(
            self.metadata, self.artifacts, tax_extractor=FakeExtractor()
        )
        self.service.put_profile(AY, CUSTOMER_ID, complete_profile(), None)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = io.BytesIO()
        writer.write(output)
        for name in ("Form 16 AY 2026-27.pdf", "AIS AY 2026-27.pdf"):
            self.service.auto_upload_document(
                AY, CUSTOMER_ID, name, output.getvalue(), "application/pdf", "user"
            )

        result = self.service.extract_and_calculate(
            AY, CUSTOMER_ID, compare_new=True, actor="reviewer"
        )

        self.assertEqual(result.reconciled.gross_salary, 2_000_000)
        self.assertEqual(result.reconciled.deposit_interest, 40_000)
        self.assertGreater(result.maximum_useful_donation_50_percent_limited, 0)
        self.assertLessEqual(
            result.old_after_donation.total_tax,
            result.old_before_donation.total_tax,
        )
        self.assertIsNotNone(result.new_regime)

    def test_valid_pdf_is_hashed_and_indexed(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = io.BytesIO()
        writer.write(output)

        document = self.service.upload_document(
            AY,
            CUSTOMER_ID,
            "form16",
            "Form 16.pdf",
            output.getvalue(),
            "user-1",
        )

        self.assertEqual(document.page_count, 1)
        self.assertEqual(len(document.sha256), 64)
        self.assertEqual(len(self.service.list_documents(AY, CUSTOMER_ID)), 1)

    def test_encrypted_ais_uses_profile_pan_and_dob_without_env_password(self):
        self.service.put_profile(AY, CUSTOMER_ID, complete_profile(), None)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("abcde1234f01011990")
        output = io.BytesIO()
        writer.write(output)

        document = self.service.upload_document(
            AY,
            CUSTOMER_ID,
            "ais",
            "AIS.pdf",
            output.getvalue(),
            "user-1",
        )

        self.assertEqual(document.page_count, 1)
        self.assertIsNotNone(document.processing_object_name)
        self.assertIn(document.processing_object_name, self.artifacts.values)

    def test_auto_intake_classifies_renames_and_preserves_original(self):
        self.service.put_profile(AY, CUSTOMER_ID, complete_profile(), None)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = io.BytesIO()
        writer.write(output)

        document = self.service.auto_upload_document(
            AY,
            CUSTOMER_ID,
            "Form 16 AY 2026-27.pdf",
            output.getvalue(),
            "application/pdf",
            "user-1",
        )

        self.assertEqual(document.category, "form16")
        self.assertIn("Form_16", document.renamed_filename)
        self.assertIn("/01_source/originals/", document.object_name)
        self.assertIn("/02_extracted/renamed/", document.processing_object_name)
        self.assertIn(document.object_name, self.artifacts.values)
        self.assertIn(document.processing_object_name, self.artifacts.values)

    def test_review_and_export_require_all_gates(self):
        self.create_profile_and_return()
        self.service.calculate(AY, CUSTOMER_ID, "new")
        draft = b'{"ITR":{"ITR1":{}}}'
        self.artifacts.values[PREFIX + "04_portal_export/portal_draft.json"] = (
            draft,
            "application/json",
            50,
        )
        self.metadata.update_state(
            AY,
            CUSTOMER_ID,
            {"portal_draft_generation": 50, "schema_valid": True},
        )

        with self.assertRaises(FilingValidationError):
            self.service.export_portal_json(AY, CUSTOMER_ID)

        approved = self.service.review(
            AY,
            CUSTOMER_ID,
            ReviewDecision(
                decision="approve",
                notes="Reviewed against the official utility.",
                portal_validation_completed=True,
            ),
            "reviewer-1",
        )
        payload, filename = self.service.export_portal_json(AY, CUSTOMER_ID)

        self.assertTrue(approved.preparer_approved)
        self.assertEqual(payload, draft)
        self.assertTrue(filename.endswith(".json"))


if __name__ == "__main__":
    unittest.main()
