#!/usr/bin/env python3
"""Generate separate old- and new-regime ITR-1 workpaper PDFs."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from itr_agent.generate_itr_workpaper import rupees, table
from itr_backend.filing_models import NormalizedReturnData
from itr_backend.tax_years import get_tax_year


EVIDENCE_ROWS = [
    ("80C – LIC life-insurance premium", 63_238, "Premium-paid statement found"),
    ("80C – eligible tuition fees", 62_000, "FY 2025-26 tuition receipts found"),
    ("80C – combined", 125_238, "Within Rs 1,50,000 cap"),
    ("80CCD(1B) – additional NPS", 0, "No receipt found"),
    ("80CCD(2) – employer NPS", 0, "No evidence found"),
    ("80D – health-insurance premium", 16_348, "Receipt and policy evidence found"),
    ("80DD", 0, "No receipt/certificate found"),
    ("80DDB", 0, "No receipt/certificate found"),
    ("80E – education-loan interest", 0, "No certificate found"),
    ("80EE / 80EEA – housing-loan interest", 0, "No certificate found"),
    ("80EEB – electric-vehicle loan interest", 0, "No certificate found"),
    ("80G – proposed eligible deduction", 108_220, "Receipt/Form 10BE pending"),
    ("80GGA", 0, "No receipt found"),
    ("80GGC", 0, "No receipt found"),
    ("80TTA – savings interest", 4_692, "AIS; capped to actual savings interest"),
    ("80TTB", 0, "Not used for below-60 age band"),
    ("80U", 0, "No disability certificate found"),
]


def build_report(data: NormalizedReturnData, regime: str, output: Path) -> None:
    result = get_tax_year(data.assessment_year).calculate(data, regime)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RegimeTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#153E5C"),
        fontSize=18,
        leading=22,
    )
    small = ParagraphStyle(
        "RegimeSmall", parent=styles["BodyText"], fontSize=8.5, leading=11
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"ITR-1 {regime.title()} Regime Workpaper",
    )
    story = [
        Paragraph(
            f"ITR-1 {regime.title()} Regime Calculation",
            title_style,
        ),
        Paragraph(
            "FY 2025-26 / AY 2026-27 · Generated "
            + datetime.now().strftime("%d %B %Y"),
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("Tax calculation", styles["Heading2"]),
        table(
            [
                ["Particular", "Amount"],
                ["Gross total income", rupees(result.gross_total_income)],
                ["Chapter VI-A deductions claimed", rupees(result.total_deductions)],
                ["Total income (rounded)", rupees(result.total_income)],
                ["Income tax before cess", rupees(result.normal_rate_tax + result.special_rate_tax)],
                ["Rebate under Section 87A", rupees(result.rebate_87a)],
                ["Health & education cess", rupees(result.cess)],
                ["Total tax liability", rupees(result.total_tax)],
                ["TDS / taxes paid", rupees(result.taxes_paid)],
                ["Balance payable", rupees(result.balance_payable)],
                ["Refund", rupees(result.refund)],
            ],
            [92 * mm, 70 * mm],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Income and tax-paid particulars", styles["Heading2"]),
        table(
            [
                ["Particular", "Amount", "Evidence"],
                ["Gross salary", rupees(2_355_971), "Form 16 and AIS reconciled"],
                ["Savings-bank interest", rupees(4_692), "AIS aggregate"],
                ["TDS on salary", rupees(281_060), "Form 16 and AIS reconciled"],
                ["Other income", "NIL", "No supporting receipt found"],
                ["House-property income/loss", "NIL", "No supporting receipt found"],
                ["Capital gains", "NIL", "No supporting receipt found"],
            ],
            [66 * mm, 35 * mm, 61 * mm],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Deduction particulars", styles["Heading2"]),
    ]

    deduction_rows = [["Section / deduction", "Claim", "Evidence / treatment"]]
    for label, amount, evidence in EVIDENCE_ROWS:
        if regime == "old":
            claim = rupees(amount) if amount else "NIL"
            treatment = evidence
        elif label.startswith("80CCD(2)"):
            claim = "NIL"
            treatment = "No evidence found; potentially allowable under new regime if evidenced"
        else:
            claim = "NIL"
            treatment = (
                f"Not claimable under new regime; evidence noted: {evidence}"
                if amount
                else "Not claimed"
            )
        deduction_rows.append([label, claim, treatment])
    story.extend(
        [
            table(deduction_rows, [66 * mm, 30 * mm, 66 * mm]),
            Spacer(1, 5 * mm),
        ]
    )

    if regime == "old":
        story.extend(
            [
                Paragraph("Proposed Section 80G donation", styles["Heading2"]),
                table(
                    [
                        ["Particular", "Amount / status"],
                        ["Proposed amount to be paid", rupees(230_000)],
                        ["Assumed category", "50% deduction subject to qualifying limit"],
                        ["Adjusted gross total income", rupees(2_164_385)],
                        ["10% qualifying pool", rupees(216_439)],
                        ["Donation admitted to limited pool", rupees(216_439)],
                        ["Eligible deduction at 50%", rupees(108_220)],
                        ["Payment mode", "Non-cash; cash above Rs 2,000 is not deductible"],
                        ["Required evidence", "Donee receipt, Form 10BE, 80G URN and category"],
                        ["Status", "PLANNED / NOT YET EVIDENCED"],
                    ],
                    [72 * mm, 90 * mm],
                ),
                Spacer(1, 4 * mm),
            ]
        )
    else:
        story.extend(
            [
                Paragraph("Section 80G treatment", styles["Heading2"]),
                Paragraph(
                    "The proposed Rs 2,30,000 donation is not deductible under "
                    "the new regime and has not been included in this calculation.",
                    styles["BodyText"],
                ),
                Spacer(1, 4 * mm),
            ]
        )

    story.extend(
        [
            Paragraph("Evidence exclusions and review notes", styles["Heading2"]),
            Paragraph(
                "Receipts dated after 31 March 2026 were excluded. Books, uniform "
                "and stationery charges were excluded. Only separately identified "
                "FY 2025-26 tuition fees were treated as potential Section 80C evidence.",
                styles["BodyText"],
            ),
            Spacer(1, 4 * mm),
            Paragraph(
                "Advisory workpaper only. Verify taxpayer eligibility, residency, "
                "bank details, interest/fee under sections 234A/234B/234C/234F, "
                "relief and final portal business rules in the current official utility.",
                small,
            ),
        ]
    )
    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data = NormalizedReturnData.model_validate_json(
        args.return_data.read_text(encoding="utf-8")
    )
    for regime in ("old", "new"):
        build_report(
            data,
            regime,
            args.output_dir
            / f"CHANDRU_ITR1_FY2025-26_{regime.upper()}_Regime_Calculation.pdf",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
