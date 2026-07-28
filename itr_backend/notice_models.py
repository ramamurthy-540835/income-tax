from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NoticeKind = Literal[
    "outstanding_demand",
    "section_139_9",
    "section_142_1",
    "section_143_1_a",
    "section_143_2",
    "section_144",
    "section_148_148a",
    "section_154",
    "section_245",
    "section_263",
    "section_270a_penalty",
    "section_277a",
    "other",
]
TaxpayerPosition = Literal["agree", "disagree", "partially_agree", "needs_review"]


class EvidenceReference(BaseModel):
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{32}$")
    description: str = Field(min_length=3, max_length=500)
    page_numbers: list[int] = Field(default_factory=list, max_length=50)


class NoticeCaseCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: NoticeKind
    section: str = Field(min_length=1, max_length=40)
    din: str | None = Field(default=None, max_length=100)
    notice_date: date
    response_due_date: date
    assessment_year: str
    demand_amount: Decimal | None = Field(default=None, ge=0)
    taxpayer_position: TaxpayerPosition = "needs_review"
    allegations_or_queries: list[str] = Field(min_length=1, max_length=50)
    taxpayer_facts: list[str] = Field(default_factory=list, max_length=100)
    requested_relief: str = Field(min_length=3, max_length=2000)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_dates_and_demand(self):
        if self.response_due_date < self.notice_date:
            raise ValueError("response due date cannot precede the notice date")
        if self.kind == "outstanding_demand" and self.demand_amount is None:
            raise ValueError("demand amount is required for an outstanding demand")
        return self


class NoticeCase(NoticeCaseCreate):
    case_id: str
    customer_id: str
    created_at: datetime
    created_by: str
    status: Literal["draft", "review_required", "approved"] = "draft"


class NoticeCaseList(BaseModel):
    cases: list[NoticeCase] = Field(default_factory=list)


class ResponseDraft(BaseModel):
    case_id: str
    generated_at: datetime
    subject: str
    response_text: str
    annexure_index: list[str]
    missing_information: list[str]
    risk_flags: list[str]
    portal_route: str
    submission_ready: bool = False
    professional_review_required: bool = True


class NoticeReview(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str = Field(min_length=3, max_length=4000)
    reviewed_by_professional: bool


class NoticeAnalysisRequest(BaseModel):
    assessment_year: str
    pasted_text: str = Field(min_length=20, max_length=100_000)


class NoticeAnalysis(BaseModel):
    detected_kind: NoticeKind
    detected_section: str | None = None
    din: str | None = None
    notice_date: date | None = None
    response_due_date: date | None = None
    demand_amount: Decimal | None = None
    urgency: Literal["critical", "high", "normal", "unknown"]
    summary: str
    recommended_actions: list[str]
    evidence_to_collect: list[str]
    questions_to_resolve: list[str]
    risk_flags: list[str]
    portal_route: str
    professional_review_required: bool = True
