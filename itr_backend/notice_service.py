from __future__ import annotations

import uuid
import re
from datetime import date, datetime, timezone
from decimal import Decimal

from itr_backend.audit import AuditRepository, NoopAuditRepository, new_audit_event
from itr_backend.analytics import AnalyticsRepository, NoopAnalyticsRepository
from itr_backend.filing_models import FilingProfile
from itr_backend.filing_repositories import (
    ArtifactNotFoundError,
    ArtifactRepository,
    FilingMetadataRepository,
)
from itr_backend.filing_service import FilingValidationError, _prefix
from itr_backend.models import normalize_assessment_year
from itr_backend.notice_models import (
    NoticeCase,
    NoticeCaseCreate,
    NoticeCaseList,
    NoticeReview,
    NoticeAnalysis,
    NoticeAnalysisRequest,
    ResponseDraft,
)


PORTAL_ROUTES = {
    "outstanding_demand": "Pending Actions > Response to Outstanding Demand",
    "section_245": "Pending Actions > e-Proceedings > Intimation u/s 245",
    "section_139_9": "Pending Actions > e-Proceedings > Defective Notice u/s 139(9)",
}
HIGH_RISK = {"section_144", "section_148_148a", "section_263", "section_270a_penalty", "section_277a"}

COURSES = {
    "outstanding_demand": [
        "Reconcile the demand against the filed return, intimation/order, Form 26AS, challans, and prior rectification orders.",
        "Choose agree, disagree, or partially agree only after preparing an amount-wise reconciliation.",
        "If credit is missing or an apparent mistake exists, prepare the appropriate rectification request and attach proof.",
    ],
    "section_139_9": [
        "Identify every defect code and decide whether to agree or disagree with each defect.",
        "If agreeing, correct the return using the applicable portal/offline utility within the notice period.",
        "If the time is insufficient, request an extension before the deadline.",
    ],
    "section_143_1_a": [
        "Reconcile each proposed adjustment with the return, Form 16, AIS/26AS, and deduction evidence.",
        "Respond separately to every adjustment with an exact amount and document reference.",
    ],
    "section_144": [
        "Act immediately: compile earlier notices, proof of prior responses, books/evidence requested, and a complete income reconciliation.",
        "Request an opportunity of hearing and submit missing evidence with a point-by-point explanation.",
    ],
    "section_277a": [
        "Do not make admissions or submit an improvised factual narrative.",
        "Preserve all original records and obtain immediate review from a tax advocate experienced in prosecution matters.",
        "Request the specific allegedly false entry/statement and relied-upon material before a substantive response.",
    ],
}

EVIDENCE = {
    "outstanding_demand": ["Filed ITR and acknowledgement", "Intimation/order creating the demand", "Form 26AS/AIS", "Tax challans and rectification orders"],
    "section_139_9": ["Defective-return notice with defect code", "Filed ITR JSON and acknowledgement", "Corrected schedules and supporting documents"],
    "section_143_1_a": ["Proposed-adjustment communication", "Filed return computation", "Form 16/26AS/AIS", "Receipts supporting disputed deductions"],
    "section_144": ["All prior notices and responses", "Books/statements and source documents requested", "Income and tax-credit reconciliation"],
    "section_277a": ["Exact notice/complaint and sanction material", "Original unaltered books and documents", "Document custody and preparation history"],
}


class NoticeService:
    def __init__(
        self,
        artifacts: ArtifactRepository,
        audit: AuditRepository | None = None,
        metadata: FilingMetadataRepository | None = None,
        analytics: AnalyticsRepository | None = None,
    ):
        self._artifacts = artifacts
        self._audit = audit or NoopAuditRepository()
        self._metadata = metadata
        self._analytics = analytics or NoopAnalyticsRepository()

    @staticmethod
    def _base(assessment_year: str, customer_id: str) -> str:
        return _prefix(assessment_year, customer_id) + "06_notices/"

    def _profile(self, assessment_year: str, customer_id: str) -> FilingProfile:
        name = _prefix(assessment_year, customer_id) + "02_extracted/client_profile.json"
        try:
            payload, _ = self._artifacts.read_json(name)
        except ArtifactNotFoundError as exc:
            raise FilingValidationError("complete the client profile first") from exc
        return FilingProfile.model_validate(payload)

    def create(
        self,
        assessment_year: str,
        customer_id: str,
        payload: NoticeCaseCreate,
        actor: str,
    ) -> NoticeCase:
        ay = normalize_assessment_year(assessment_year)
        if normalize_assessment_year(payload.assessment_year) != ay:
            raise FilingValidationError("notice assessment year does not match workspace")
        self._profile(ay, customer_id)
        if self._metadata and payload.evidence:
            available = {
                document.document_id
                for document in self._metadata.list_documents(ay, customer_id)
            }
            unknown = [
                evidence.document_id
                for evidence in payload.evidence
                if evidence.document_id not in available
            ]
            if unknown:
                raise FilingValidationError(
                    "evidence document does not belong to this client workspace"
                )
        case = NoticeCase(
            **payload.model_dump(),
            case_id=f"ntc_{uuid.uuid4().hex}",
            customer_id=customer_id,
            created_at=datetime.now(timezone.utc),
            created_by=actor,
        )
        base = self._base(ay, customer_id)
        self._artifacts.write_json(
            f"{base}{case.case_id}/case.json", case.model_dump(mode="json"), None
        )
        try:
            index, generation = self._artifacts.read_json(base + "index.json")
        except ArtifactNotFoundError:
            index, generation = {"case_ids": []}, None
        index["case_ids"].append(case.case_id)
        self._artifacts.write_json(base + "index.json", index, generation)
        self._audit.append(
            new_audit_event(ay, customer_id, "notice.created", actor, {"case_id": case.case_id, "kind": case.kind})
        )
        self._analytics.record(
            "notices",
            {
                "case_id": case.case_id,
                "customer_id": customer_id,
                "assessment_year": ay,
                "kind": case.kind,
                "section": case.section,
                "din": case.din,
                "notice_date": case.notice_date.isoformat(),
                "response_due_date": case.response_due_date.isoformat(),
                "demand_amount": (
                    str(case.demand_amount) if case.demand_amount is not None else None
                ),
                "status": case.status,
                "event_at": case.created_at.isoformat(),
            },
        )
        return case

    def analyze(self, request: NoticeAnalysisRequest) -> NoticeAnalysis:
        normalize_assessment_year(request.assessment_year)
        text = request.pasted_text
        lower = text.lower()
        section_match = re.search(
            r"(?:u/s|under\s+section|section)\s*([0-9]{2,3}[a-zA-Z]?(?:\s*\(\s*[0-9a-zA-Z]+\s*\))?)",
            text,
            re.I,
        )
        section = re.sub(r"\s+", "", section_match.group(1)) if section_match else None
        normalized_section = (section or "").upper()
        if "277A" in normalized_section:
            kind = "section_277a"
        elif normalized_section.startswith("139(9"):
            kind = "section_139_9"
        elif normalized_section.startswith("143(1"):
            kind = "section_143_1_a"
        elif normalized_section.startswith("142(1"):
            kind = "section_142_1"
        elif normalized_section.startswith("143(2"):
            kind = "section_143_2"
        elif normalized_section == "144" or "best judgment" in lower:
            kind = "section_144"
        elif normalized_section.startswith("148"):
            kind = "section_148_148a"
        elif normalized_section == "154":
            kind = "section_154"
        elif normalized_section == "245":
            kind = "section_245"
        elif normalized_section == "263":
            kind = "section_263"
        elif normalized_section.startswith("270A"):
            kind = "section_270a_penalty"
        elif "outstanding demand" in lower or normalized_section == "156":
            kind = "outstanding_demand"
        else:
            kind = "other"
        din_match = re.search(r"\bDIN\s*[:\-]?\s*([A-Z0-9/_-]{8,100})", text, re.I)
        date_values: list[date] = []
        for day, month, year in re.findall(
            r"\b([0-3]?\d)[-/]([01]?\d)[-/](20\d{2})\b", text
        ):
            try:
                date_values.append(date(int(year), int(month), int(day)))
            except ValueError:
                continue
        notice_date = date_values[0] if date_values else None
        due_match = re.search(
            r"(?:on or before|due date|by)\s*[:\-]?\s*([0-3]?\d)[-/]([01]?\d)[-/](20\d{2})",
            text,
            re.I,
        )
        due_date = None
        if due_match:
            try:
                due_date = date(
                    int(due_match.group(3)),
                    int(due_match.group(2)),
                    int(due_match.group(1)),
                )
            except ValueError:
                pass
        amount_match = re.search(
            r"(?:demand\s+amount(?:\s+payable)?|amount\s+payable|tax\s+payable)"
            r"[^₹\d]{0,20}(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)",
            text,
            re.I,
        )
        demand = (
            Decimal(amount_match.group(1).replace(",", "")) if amount_match else None
        )
        days = (due_date - date.today()).days if due_date else None
        urgency = (
            "critical" if days is not None and days <= 3
            else "high" if days is not None and days <= 10
            else "normal" if days is not None
            else "unknown"
        )
        actions = COURSES.get(
            kind,
            [
                "Authenticate the DIN and download the complete communication from the e-Filing portal.",
                "Map every query to verified facts and supporting evidence before drafting a response.",
                "Confirm the statutory section, deadline, and available remedy with a tax professional.",
            ],
        )
        evidence = EVIDENCE.get(
            kind,
            ["Complete notice/order", "Filed return and computation", "AIS/26AS", "Documents supporting each factual response"],
        )
        questions = []
        if not section:
            questions.append("What section is printed on the notice?")
        if not due_date:
            questions.append("What is the exact response deadline shown on the portal/notice?")
        if kind == "outstanding_demand" and demand is None:
            questions.append("What is the exact outstanding demand amount and assessment year?")
        risks = []
        if urgency == "critical":
            risks.append("Deadline is due or within three days; escalate immediately.")
        if kind in HIGH_RISK:
            risks.append("High-risk proceeding requiring professional review before any substantive response.")
        if kind == "section_277a":
            risks.append("Potential prosecution exposure; preserve originals and avoid unsupported admissions.")
        return NoticeAnalysis(
            detected_kind=kind,
            detected_section=section,
            din=din_match.group(1) if din_match else None,
            notice_date=notice_date,
            response_due_date=due_date,
            demand_amount=demand,
            urgency=urgency,
            summary=(
                f"Detected {kind.replace('_', ' ')}"
                + (f" under section {section}" if section else "")
                + (f" with stated amount Rs {demand:,.2f}" if demand is not None else "")
                + "."
            ),
            recommended_actions=actions,
            evidence_to_collect=evidence,
            questions_to_resolve=questions,
            risk_flags=risks,
            portal_route=PORTAL_ROUTES.get(
                kind, "Pending Actions > e-Proceedings > For Your Action"
            ),
        )

    def get(self, assessment_year: str, customer_id: str, case_id: str) -> NoticeCase:
        if not case_id.startswith("ntc_"):
            raise ValueError("invalid notice case ID")
        try:
            payload, _ = self._artifacts.read_json(
                self._base(assessment_year, customer_id) + f"{case_id}/case.json"
            )
        except ArtifactNotFoundError as exc:
            raise FilingValidationError("notice case not found") from exc
        return NoticeCase.model_validate(payload)

    def list(self, assessment_year: str, customer_id: str) -> NoticeCaseList:
        base = self._base(assessment_year, customer_id)
        try:
            index, _ = self._artifacts.read_json(base + "index.json")
        except ArtifactNotFoundError:
            return NoticeCaseList()
        return NoticeCaseList(
            cases=[self.get(assessment_year, customer_id, case_id) for case_id in index.get("case_ids", [])]
        )

    def draft(
        self, assessment_year: str, customer_id: str, case_id: str, actor: str
    ) -> ResponseDraft:
        case = self.get(assessment_year, customer_id, case_id)
        profile = self._profile(assessment_year, customer_id)
        taxpayer = profile.taxpayer
        missing = []
        if not taxpayer.pan:
            missing.append("Taxpayer PAN")
        if not case.din:
            missing.append("Document Identification Number (DIN)")
        if not case.taxpayer_facts:
            missing.append("Verified taxpayer facts addressing each allegation/query")
        if not case.evidence:
            missing.append("Evidence references with document and page details")
        risks = []
        if case.kind in HIGH_RISK:
            risks.append("High-risk proceeding: obtain review by a tax professional/advocate before submission.")
        if case.kind == "section_277a":
            risks.append("Potential prosecution provision: do not make admissions or factual assertions without legal review.")
        if case.taxpayer_position == "needs_review":
            risks.append("Taxpayer position has not been finalized.")
        facts = "\n".join(f"{i}. {fact}" for i, fact in enumerate(case.taxpayer_facts, 1)) or "[Verified facts required]"
        queries = "\n".join(f"{i}. {query}" for i, query in enumerate(case.allegations_or_queries, 1))
        annexures = [
            f"Annexure {i}: {e.description} (document {e.document_id}"
            + (f", pages {', '.join(map(str, e.page_numbers))}" if e.page_numbers else "")
            + ")"
            for i, e in enumerate(case.evidence, 1)
        ]
        if case.kind == "section_277a":
            body = (
                "This is a preliminary response without prejudice. The taxpayer requests the complete "
                "material relied upon, a clear statement of the alleged false entry or statement, and "
                "reasonable time for inspection and a legally reviewed response. No adverse inference "
                "or admission should be drawn from this preliminary communication."
            )
        else:
            body = (
                f"With reference to the notice dated {case.notice_date:%d-%m-%Y} under section "
                f"{case.section}, the taxpayer submits the following response.\n\n"
                f"Queries / proposed adjustments\n{queries}\n\n"
                f"Verified factual response\n{facts}\n\n"
                f"Position: {case.taxpayer_position.replace('_', ' ')}.\n"
                f"Relief requested: {case.requested_relief}\n\n"
                "The enclosed evidence is cross-referenced in the annexure index. The taxpayer "
                "requests that the record be considered and an opportunity of hearing be provided "
                "before any adverse conclusion."
            )
        draft = ResponseDraft(
            case_id=case_id,
            generated_at=datetime.now(timezone.utc),
            subject=f"Response to notice under section {case.section} for {case.assessment_year}",
            response_text=body,
            annexure_index=annexures,
            missing_information=missing,
            risk_flags=risks,
            portal_route=PORTAL_ROUTES.get(case.kind, "Pending Actions > e-Proceedings > For Your Action"),
            submission_ready=False,
        )
        self._artifacts.write_json(
            self._base(assessment_year, customer_id) + f"{case_id}/response_draft.json",
            draft.model_dump(mode="json"),
            None,
        )
        self._audit.append(
            new_audit_event(normalize_assessment_year(assessment_year), customer_id, "notice.response_drafted", actor, {"case_id": case_id})
        )
        self._analytics.record(
            "responses",
            {
                "case_id": case_id,
                "customer_id": customer_id,
                "assessment_year": normalize_assessment_year(assessment_year),
                "submission_ready": draft.submission_ready,
                "professional_review_required": draft.professional_review_required,
                "object_name": self._base(assessment_year, customer_id)
                + f"{case_id}/response_draft.json",
                "event_at": draft.generated_at.isoformat(),
            },
        )
        return draft

    def review(
        self,
        assessment_year: str,
        customer_id: str,
        case_id: str,
        review: NoticeReview,
        actor: str,
    ) -> ResponseDraft:
        base = self._base(assessment_year, customer_id) + f"{case_id}/"
        try:
            payload, generation = self._artifacts.read_json(base + "response_draft.json")
        except ArtifactNotFoundError as exc:
            raise FilingValidationError("generate a response draft before review") from exc
        draft = ResponseDraft.model_validate(payload)
        if review.decision == "approve":
            if not review.reviewed_by_professional:
                raise FilingValidationError("professional review confirmation is required")
            if draft.missing_information:
                raise FilingValidationError("resolve missing information before approval")
            draft.submission_ready = True
        else:
            draft.submission_ready = False
        self._artifacts.write_json(base + "response_draft.json", draft.model_dump(mode="json"), generation)
        self._artifacts.write_json(base + "review.json", {**review.model_dump(mode="json"), "actor": actor, "reviewed_at": datetime.now(timezone.utc).isoformat()}, None)
        return draft
