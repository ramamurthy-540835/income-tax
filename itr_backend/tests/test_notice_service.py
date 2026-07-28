from __future__ import annotations

import unittest
from datetime import date

from itr_backend.notice_models import (
    NoticeAnalysisRequest,
    NoticeCaseCreate,
    NoticeReview,
)
from itr_backend.notice_service import NoticeService
from itr_backend.tests.test_filing_service import (
    AY,
    CUSTOMER_ID,
    InMemoryArtifacts,
    PREFIX,
    complete_profile,
)
from itr_backend.filing_service import FilingValidationError


class NoticeServiceTests(unittest.TestCase):
    def setUp(self):
        self.artifacts = InMemoryArtifacts()
        self.artifacts.write_json(
            PREFIX + "02_extracted/client_profile.json",
            complete_profile().model_dump(mode="json"),
            None,
        )
        self.service = NoticeService(self.artifacts)

    def payload(self, kind: str = "outstanding_demand") -> NoticeCaseCreate:
        return NoticeCaseCreate(
            kind=kind,
            section="156",
            din="DIN123",
            notice_date=date(2026, 7, 1),
            response_due_date=date(2026, 7, 30),
            assessment_year=AY,
            demand_amount=10000,
            taxpayer_position="disagree",
            allegations_or_queries=["Demand does not give credit for TDS."],
            taxpayer_facts=["Form 26AS reflects TDS credit of Rs 10,000."],
            requested_relief="Delete the demand after allowing verified TDS credit.",
        )

    def test_create_list_and_draft_notice_response(self):
        case = self.service.create(AY, CUSTOMER_ID, self.payload(), "preparer")
        listed = self.service.list(AY, CUSTOMER_ID)
        draft = self.service.draft(AY, CUSTOMER_ID, case.case_id, "preparer")

        self.assertEqual(len(listed.cases), 1)
        self.assertIn("verified TDS", draft.response_text)
        self.assertFalse(draft.submission_ready)
        self.assertIn("Response to Outstanding Demand", draft.portal_route)

    def test_section_277a_generates_only_protective_preliminary_response(self):
        payload = self.payload("section_277a").model_copy(
            update={"section": "277A", "demand_amount": None}
        )
        case = self.service.create(AY, CUSTOMER_ID, payload, "preparer")
        draft = self.service.draft(AY, CUSTOMER_ID, case.case_id, "preparer")

        self.assertIn("without prejudice", draft.response_text)
        self.assertTrue(any("prosecution" in flag.lower() for flag in draft.risk_flags))

    def test_approval_fails_when_evidence_or_risk_flags_remain(self):
        case = self.service.create(AY, CUSTOMER_ID, self.payload(), "preparer")
        self.service.draft(AY, CUSTOMER_ID, case.case_id, "preparer")

        with self.assertRaises(FilingValidationError):
            self.service.review(
                AY,
                CUSTOMER_ID,
                case.case_id,
                NoticeReview(
                    decision="approve",
                    notes="Reviewed",
                    reviewed_by_professional=True,
                ),
                "reviewer",
            )

    def test_pasted_demand_is_analyzed_into_course_and_evidence(self):
        analysis = self.service.analyze(
            NoticeAnalysisRequest(
                assessment_year=AY,
                pasted_text=(
                    "Notice of outstanding demand under section 156. "
                    "DIN: ITBA/DEM/12345678 dated 01/07/2026. "
                    "Demand amount payable Rs. 45,600. "
                    "Submit response on or before 30/07/2026."
                ),
            )
        )

        self.assertEqual(analysis.detected_kind, "outstanding_demand")
        self.assertEqual(analysis.demand_amount, 45600)
        self.assertTrue(analysis.recommended_actions)
        self.assertIn("Form 26AS/AIS", analysis.evidence_to_collect)

    def test_pasted_section_277a_is_flagged_for_prosecution_review(self):
        analysis = self.service.analyze(
            NoticeAnalysisRequest(
                assessment_year=AY,
                pasted_text=(
                    "Show cause notice under section 277A regarding alleged "
                    "falsification of books. DIN: ITBA/PROS/12345678."
                ),
            )
        )

        self.assertEqual(analysis.detected_kind, "section_277a")
        self.assertTrue(any("prosecution" in flag.lower() for flag in analysis.risk_flags))
