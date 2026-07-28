from __future__ import annotations

import json
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from google import genai
from google.genai import types

from itr_backend.filing_models import (
    ExtractedTaxFacts,
    ReconciledTaxFacts,
)

EXTRACTION_PROMPT = """
Extract Indian individual income-tax evidence from this single document for
FY 2025-26 / AY 2026-27. Return exactly one JSON object with:
document_type, issuer, financial_year, assessment_year, taxpayer_name,
gross_salary, exempt_salary_allowances, professional_tax, savings_interest,
deposit_interest, dividend_income, tds_salary, tds_other, section_80c,
section_80d, section_80tta, evidence_quality, notes.

Rules:
- Return zero for amounts not printed; never estimate or project.
- For Form 16 use annual values, not duplicated monthly/detail rows.
- For AIS use accepted/aggregate values and do not add summary plus transaction rows.
- A receipt/policy is deduction evidence only when payment and relevant FY are shown.
- 80C must contain eligible paid amount, capped later by the tax engine.
- 80D must contain supported eligible premium, not sum insured.
- Do not expose PAN, Aadhaar, bank account, address, phone, or email.
- evidence_quality must be high, medium, or low.
""".strip()


class TaxDocumentExtractor(Protocol):
    def extract(
        self, document_id: str, payload: bytes, mime_type: str
    ) -> ExtractedTaxFacts: ...


class GeminiTaxDocumentExtractor:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is required once at backend level for automatic extraction"
            )
        self._client = genai.Client(api_key=key)
        self._model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    def extract(
        self, document_id: str, payload: bytes, mime_type: str
    ) -> ExtractedTaxFacts:
        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=payload, mime_type=mime_type),
                EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        text = response.text.strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("document extractor did not return JSON")
        value = json.loads(text[start : end + 1])
        value["document_id"] = document_id
        return ExtractedTaxFacts.model_validate(value)


def rupee(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def reconcile(facts: list[ExtractedTaxFacts]) -> ReconciledTaxFacts:
    relevant = [
        item for item in facts
        if item.assessment_year in {None, "", "2026-27", "AY_2026-27"}
        and item.financial_year in {None, "", "2025-26", "FY_2025-26"}
    ]
    warnings: list[str] = []
    if len(relevant) != len(facts):
        warnings.append("Documents outside FY 2025-26 / AY 2026-27 were excluded.")
    form16 = [x for x in relevant if "form 16" in x.document_type.lower()]
    ais = [x for x in relevant if "annual information" in x.document_type.lower() or x.document_type.lower() == "ais"]
    salary_form16 = sum((x.gross_salary for x in form16), Decimal("0"))
    salary_ais = max((x.gross_salary for x in ais), default=Decimal("0"))
    salary = max(salary_form16, salary_ais)
    if salary_form16 and salary_ais and salary_form16 != salary_ais:
        warnings.append(
            "Form 16 and AIS salary totals differ; the higher supported aggregate "
            "was used and requires reconciliation."
        )
    tds_form16 = sum((x.tds_salary for x in form16), Decimal("0"))
    tds_ais = max((x.tds_salary for x in ais), default=Decimal("0"))
    if tds_form16 and tds_ais and tds_form16 != tds_ais:
        warnings.append("Form 16 and AIS salary-TDS totals differ; verify Form 26AS.")
    def preferred(field: str) -> Decimal:
        ais_value = max((getattr(x, field) for x in ais), default=Decimal("0"))
        return ais_value or max(
            (getattr(x, field) for x in relevant), default=Decimal("0")
        )
    non_ais = [x for x in relevant if x not in ais]
    section_80c = max(
        (x.section_80c for x in non_ais), default=Decimal("0")
    )
    section_80d = max(
        (x.section_80d for x in non_ais), default=Decimal("0")
    )
    if sum(1 for x in non_ais if x.section_80c) > 1:
        warnings.append(
            "Multiple documents report Section 80C; the highest supported total "
            "was used to avoid duplicate counting."
        )
    if sum(1 for x in non_ais if x.section_80d) > 1:
        warnings.append(
            "Multiple documents report Section 80D; the highest supported total "
            "was used to avoid duplicate counting."
        )
    return ReconciledTaxFacts(
        gross_salary=rupee(salary),
        exempt_salary_allowances=rupee(sum((x.exempt_salary_allowances for x in form16), Decimal("0"))),
        professional_tax=rupee(sum((x.professional_tax for x in form16), Decimal("0"))),
        savings_interest=rupee(preferred("savings_interest")),
        deposit_interest=rupee(preferred("deposit_interest")),
        dividend_income=rupee(preferred("dividend_income")),
        tds_salary=rupee(max(tds_form16, tds_ais)),
        tds_other=rupee(preferred("tds_other")),
        section_80c=min(150000, rupee(section_80c)),
        section_80d=rupee(section_80d),
        section_80tta=min(10000, rupee(preferred("section_80tta") or preferred("savings_interest"))),
        source_document_ids=[x.document_id for x in relevant],
        warnings=warnings,
    )
