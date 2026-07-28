#!/usr/bin/env python3
"""Generate separate Arun FY 2025-26 old/new regime workpapers."""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from itr_agent.generate_itr_workpaper import rupees, table
from itr_backend.filing_models import (
    DeductionDetails,
    IncomeDetails,
    NormalizedReturnData,
    TaxPaidDetails,
)
from itr_backend.tax_years import get_tax_year


SALARY = 2_638_205
SAVINGS_INTEREST = 16_729
DEPOSIT_INTEREST = 5_618
TDS_SALARY = 285_000
PROFESSIONAL_TAX = 1_250
SECTION_80C = 64_734
SECTION_80TTA = 10_000


def round_rupee(value) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate(regime: str, include_planned_donation: bool):
    section_80g = 0
    if regime == "old" and include_planned_donation:
        # 10% of adjusted GTI, 50%-with-limit category, rounded to rupees.
        adjusted_gti = (
            SALARY
            - 50_000
            - PROFESSIONAL_TAX
            + SAVINGS_INTEREST
            + DEPOSIT_INTEREST
            - SECTION_80C
            - SECTION_80TTA
        )
        donation = round_rupee(Decimal(adjusted_gti) * Decimal("0.10"))
        section_80g = round_rupee(Decimal(donation) * Decimal("0.50"))
    data = NormalizedReturnData(
        assessment_year="AY_2026-27",
        age_band="below_60",
        income=IncomeDetails(
            gross_salary=SALARY,
            professional_tax=PROFESSIONAL_TAX,
            savings_interest=SAVINGS_INTEREST,
            deposit_interest=DEPOSIT_INTEREST,
        ),
        deductions=DeductionDetails(
            section_80c_80ccc_80ccd1=SECTION_80C,
            section_80g=section_80g,
            section_80tta=SECTION_80TTA,
        ),
        tax_paid=TaxPaidDetails(tds_salary=TDS_SALARY),
    )
    return get_tax_year("AY_2026-27").calculate(data, regime), data


def build(output: Path, regime: str) -> None:
    baseline_result, baseline_data = calculate(regime, include_planned_donation=False)
    donation_result, donation_data = calculate(
        regime, include_planned_donation=(regime == "old")
    )
    result = baseline_result
    data = donation_data if regime == "old" else baseline_data
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ArunTitle", parent=styles["Title"], alignment=TA_CENTER,
        textColor=colors.HexColor("#153E5C"), fontSize=18, leading=22,
    )
    small = ParagraphStyle(
        "ArunSmall", parent=styles["BodyText"], fontSize=8.5, leading=11
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"Arun {regime.title()} Regime ITR-1 Workpaper",
    )
    story = [
        Paragraph(f"Arun – {regime.title()} Regime Calculation", title),
        Paragraph("FY 2025-26 / AY 2026-27", styles["Normal"]),
        Spacer(1, 5 * mm),
        Paragraph("Tax calculation", styles["Heading2"]),
        table(
            [
                ["Particular", "Amount"],
                ["Gross salary – two employers", rupees(SALARY)],
                ["Savings-bank interest", rupees(SAVINGS_INTEREST)],
                ["Term-deposit interest", rupees(DEPOSIT_INTEREST)],
                ["Gross total income", rupees(result.gross_total_income)],
                ["Chapter VI-A deductions (before donation)", rupees(result.total_deductions)],
                ["Total income (rounded)", rupees(result.total_income)],
                ["Income tax before cess", rupees(result.normal_rate_tax)],
                ["Rebate under Section 87A", rupees(result.rebate_87a)],
                ["Health & education cess", rupees(result.cess)],
                ["Tax liability before donation", rupees(result.total_tax)],
                ["Salary TDS credit", rupees(result.taxes_paid)],
                ["Balance payable before donation", rupees(result.balance_payable)],
                ["Refund", rupees(result.refund)],
            ],
            [92 * mm, 70 * mm],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Deduction evidence", styles["Heading2"]),
    ]
    evidence = [
        ("80C – employee PF / Form 16", SECTION_80C, "Form 16 and Feb/Mar payroll evidence"),
        ("80CCD(1B)", 0, "No receipt found"),
        ("80CCD(2)", 0, "No evidence found"),
        ("80D", 0, "No receipt found"),
        ("80DD", 0, "No evidence found"),
        ("80DDB", 0, "No evidence found"),
        ("80E", 0, "No evidence found"),
        ("80EE / 80EEA", 0, "No certificate found"),
        ("80EEB", 0, "No certificate found"),
        ("80G", int(data.deductions.section_80g), "Planned; receipt/Form 10BE pending"),
        ("80GGA", 0, "No receipt found"),
        ("80GGC", 0, "No receipt found"),
        ("80TTA", SECTION_80TTA, "AIS savings interest; statutory cap"),
        ("80TTB", 0, "Below-60 assumption"),
        ("80U", 0, "No evidence found"),
    ]
    rows = [["Section", "Claim", "Evidence / treatment"]]
    for label, amount, note in evidence:
        if regime == "new":
            claim = "NIL"
            treatment = (
                "No evidence found; allowable if evidenced"
                if label.startswith("80CCD(2)")
                else "Not claimable under new regime"
            )
        else:
            claim = rupees(amount) if amount else "NIL"
            treatment = note
        rows.append([label, claim, treatment])
    story.extend([table(rows, [66 * mm, 30 * mm, 66 * mm]), Spacer(1, 5 * mm)])

    if regime == "old":
        adjusted_gti = (
            SALARY - 50_000 - PROFESSIONAL_TAX
            + SAVINGS_INTEREST + DEPOSIT_INTEREST
            - SECTION_80C - SECTION_80TTA
        )
        donation = round_rupee(Decimal(adjusted_gti) * Decimal("0.10"))
        eligible = round_rupee(Decimal(donation) * Decimal("0.50"))
        story.extend(
            [
                Paragraph("80G donation planning", styles["Heading2"]),
                table(
                    [
                        ["Particular", "Amount / result"],
                        ["Assumed category", "50% deduction subject to 10% adjusted-GTI limit"],
                        ["Adjusted gross total income", rupees(adjusted_gti)],
                        ["Maximum useful donation", rupees(donation)],
                        ["Eligible 80G deduction", rupees(eligible)],
                        ["Total deductions after donation", rupees(donation_result.total_deductions)],
                        ["Total income after donation", rupees(donation_result.total_income)],
                        ["Tax before donation", rupees(baseline_result.total_tax)],
                        ["Tax after maximum eligible donation", rupees(donation_result.total_tax)],
                        ["Tax reduction from donation", rupees(baseline_result.total_tax - donation_result.total_tax)],
                        ["Taxes already paid", rupees(donation_result.taxes_paid)],
                        ["Remaining payable after donation", rupees(donation_result.balance_payable)],
                        ["Extra donation beyond ceiling", "Permitted, but gives no additional 80G deduction"],
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
                Paragraph("80G treatment", styles["Heading2"]),
                Paragraph(
                    "Section 80G is not deductible under the new regime and is "
                    "not included in this calculation.",
                    styles["BodyText"],
                ),
                Spacer(1, 4 * mm),
            ]
        )
    story.extend(
        [
            Paragraph("Review notes", styles["Heading2"]),
            Paragraph(
                "Assumptions: resident individual below age 60; no HRA exemption "
                "claimed because rent evidence was not supplied. Salary from the "
                "first employer is supported by AIS but its readable Form 16 was "
                "not supplied. The Section 194-IA property-purchase entry is not "
                "treated as Arun's tax credit. FY 2026-27 documents are excluded.",
                styles["BodyText"],
            ),
            Spacer(1, 4 * mm),
            Paragraph(
                "Advisory workpaper only. Reconcile Form 26AS, both employers' "
                "Form 16 records, taxpayer eligibility, DOB/residency, bank accounts, "
                "interest/fees and official portal business rules before filing.",
                small,
            ),
        ]
    )
    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for regime in ("old", "new"):
        build(
            args.output_dir
            / f"ARUN_ITR1_FY2025-26_{regime.upper()}_Regime_Calculation.pdf",
            regime,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
