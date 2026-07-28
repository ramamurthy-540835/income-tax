#!/usr/bin/env python3
"""Generate an advisory ITR-1 calculation and evidence workpaper PDF."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from itr_backend.filing_models import NormalizedReturnData
from itr_backend.tax_years import get_tax_year


def rupees(value: int) -> str:
    return f"Rs {value:,.0f}"


def table(rows, widths=None):
    header_style = ParagraphStyle(
        "TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=colors.white,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=8.5,
        leading=10,
    )
    first_column_style = ParagraphStyle(
        "TableFirstColumn",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )
    wrapped = []
    for row_number, row in enumerate(rows):
        wrapped.append(
            [
                Paragraph(
                    str(value),
                    header_style
                    if row_number == 0
                    else first_column_style
                    if column_number == 0
                    else cell_style,
                )
                for column_number, value in enumerate(row)
            ]
        )
    result = Table(wrapped, colWidths=widths, repeatRows=1)
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153E5C")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9AA8B2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F8")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = NormalizedReturnData.model_validate_json(
        args.return_data.read_text(encoding="utf-8")
    )
    policy = get_tax_year(data.assessment_year)
    old = policy.calculate(data, "old")
    new = policy.calculate(data, "new")
    preferred = old if old.total_tax < new.total_tax else new
    saving = abs(old.total_tax - new.total_tax)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            textColor=colors.HexColor("#153E5C"),
            fontSize=18,
            leading=22,
        )
    )
    small = ParagraphStyle(
        "Small", parent=styles["BodyText"], fontSize=8.5, leading=11
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(args.output),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="ITR-1 Tax Calculation and Deduction Evidence Workpaper",
    )
    story = [
        Paragraph("ITR-1 Tax Calculation & Evidence Workpaper", styles["ReportTitle"]),
        Paragraph(
            "FY 2025-26 / AY 2026-27 · Generated "
            + datetime.now().strftime("%d %B %Y"),
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("Executive result", styles["Heading2"]),
        table(
            [
                ["Particular", "Old regime", "New regime"],
                ["Gross total income", rupees(old.gross_total_income), rupees(new.gross_total_income)],
                ["Chapter VI-A deductions", rupees(old.total_deductions), rupees(new.total_deductions)],
                ["Total income (rounded)", rupees(old.total_income), rupees(new.total_income)],
                ["Income tax before cess", rupees(old.normal_rate_tax + old.special_rate_tax), rupees(new.normal_rate_tax + new.special_rate_tax)],
                ["Health & education cess", rupees(old.cess), rupees(new.cess)],
                ["Total tax", rupees(old.total_tax), rupees(new.total_tax)],
                ["TDS / taxes paid", rupees(old.taxes_paid), rupees(new.taxes_paid)],
                ["Balance payable", rupees(old.balance_payable), rupees(new.balance_payable)],
            ],
            [66 * mm, 48 * mm, 48 * mm],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            f"<b>Lower-tax result:</b> {preferred.regime.title()} regime, lower by "
            f"{rupees(saving)} on the evidenced and assumed figures.",
            styles["BodyText"],
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
        Paragraph("Old-regime deduction evidence", styles["Heading2"]),
        table(
            [
                ["Section / deduction", "Claim", "Evidence status"],
                ["80C – LIC life-insurance premium", rupees(63_238), "Premium-paid statement found"],
                ["80C – eligible tuition fees", rupees(62_000), "FY 2025-26 tuition receipts found"],
                ["80C – combined claim", rupees(125_238), "Within Rs 1,50,000 cap"],
                ["80CCD(1B) – additional NPS", "NIL", "No receipt found"],
                ["80CCD(2) – employer NPS", "NIL", "No evidence found"],
                ["80D – health-insurance premium", rupees(16_348), "Receipt and policy evidence found"],
                ["80DD", "NIL", "No receipt/certificate found"],
                ["80DDB", "NIL", "No receipt/certificate found"],
                ["80E – education-loan interest", "NIL", "No certificate found"],
                ["80EE / 80EEA – housing-loan interest", "NIL", "No certificate found"],
                ["80EEB – electric-vehicle loan interest", "NIL", "No certificate found"],
                ["80G – assumed eligible deduction", rupees(108_220), "Proposed donation; receipt/Form 10BE pending"],
                ["80GGA", "NIL", "No receipt found"],
                ["80GGC", "NIL", "No receipt found"],
                ["80TTA – savings interest", rupees(4_692), "AIS; capped to actual savings interest"],
                ["80TTB", "NIL", "Not used for below-60 age band"],
                ["80U", "NIL", "No disability certificate found"],
            ],
            [66 * mm, 34 * mm, 62 * mm],
        ),
        PageBreak(),
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
                ["Payment mode required", "Non-cash recommended; cash above Rs 2,000 is not deductible"],
                ["Evidence required", "Donee-issued receipt and Form 10BE; verify 80G URN and category"],
                ["Current status", "PLANNED / NOT YET EVIDENCED"],
            ],
            [72 * mm, 90 * mm],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Evidence exclusions and review notes", styles["Heading2"]),
        Paragraph(
            "School receipts dated after 31 March 2026 were excluded. Books, "
            "uniform and stationery charges were excluded; only separately "
            "identified tuition fees paid during FY 2025-26 were included. "
            "The proposed donation is not treated as filing-ready until payment "
            "evidence, the donee-issued receipt and Form 10BE are available.",
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            "This is an advisory preparation workpaper generated from uploaded "
            "documents. Interest under sections 234A/234B/234C, fee under section "
            "234F, relief, residency, eligibility answers, bank details and final "
            "portal business rules must be verified in the current official "
            "Income Tax utility before filing.",
            small,
        ),
    ]
    doc.build(story)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
