from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from itr_backend.filing_models import (
    AutomatedTaxCalculation,
    CalculationResult,
    FilingProfile,
)


def money(value: int) -> str:
    return f"Rs {value:,.0f}"


def calculation_pdf(
    profile: FilingProfile,
    result: CalculationResult,
    customer_id: str,
    automated: AutomatedTaxCalculation | None = None,
) -> bytes:
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"{result.regime.title()} regime tax calculation",
    )
    taxpayer = " ".join(
        value for value in (
            profile.taxpayer.first_name,
            profile.taxpayer.middle_name,
            profile.taxpayer.surname,
        ) if value
    ) or "Client"
    rows = [
        ["Particular", "Amount"],
        ["Gross total income", money(result.gross_total_income)],
        ["Total deductions", money(result.total_deductions)],
        ["Total income", money(result.total_income)],
        ["Normal-rate tax", money(result.normal_rate_tax)],
        ["Special-rate tax", money(result.special_rate_tax)],
        ["Section 87A rebate", money(result.rebate_87a)],
        ["Health and education cess", money(result.cess)],
        ["Total tax liability", money(result.total_tax)],
        ["Taxes paid", money(result.taxes_paid)],
        ["Balance payable", money(result.balance_payable)],
        ["Refund", money(result.refund)],
    ]
    table = Table(rows, colWidths=[105 * mm, 55 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4a37")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#b8b3a6")),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
    ]))
    story = [
        Paragraph("AIDIRAC Tax Calculation", styles["Title"]),
        Paragraph(
            f"{taxpayer} · {customer_id} · {result.assessment_year} · "
            f"{result.regime.title()} regime",
            styles["Normal"],
        ),
        Paragraph(
            f"Generated {datetime.now():%d %B %Y %H:%M}",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm), table, Spacer(1, 7 * mm),
    ]
    plan = result.donation_planning
    if result.regime == "old" and plan:
        donation_rows = [
            ["80G planning (limited categories)", "Amount"],
            ["Adjusted total income", money(plan.adjusted_total_income)],
            ["10% qualifying ceiling", money(plan.limited_category_qualifying_ceiling)],
            ["Maximum useful donation — 50% category", money(plan.max_donation_50_percent_limited)],
            ["Maximum eligible deduction — 50% category", money(plan.max_deduction_50_percent_limited)],
            ["Estimated tax saving — 50% category", money(plan.estimated_tax_saving_50_percent_limited)],
        ]
        donation_table = Table(donation_rows, colWidths=[105 * mm, 55 * mm])
        donation_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c9e76b")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#b8b3a6")),
            ("PADDING", (0, 0), (-1, -1), 7),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ]))
        story.extend([
            Paragraph("Donation planning", styles["Heading2"]),
            donation_table,
            Spacer(1, 4 * mm),
            Paragraph(
                "Donation figures are planning estimates. Claim requires payment "
                "within the relevant year, an eligible institution/category, receipt "
                "and Form 10BE. Section 80G is not available under the new regime.",
                styles["BodyText"],
            ),
        ])
    if result.regime == "old" and automated:
        comparison = Table(
            [
                ["Old-regime outcome", "Amount"],
                ["Tax before donation", money(automated.old_before_donation.total_tax)],
                [
                    "Balance payable before donation",
                    money(automated.old_before_donation.balance_payable),
                ],
                [
                    "Maximum useful donation (50% limited)",
                    money(automated.maximum_useful_donation_50_percent_limited),
                ],
                ["Eligible 80G deduction", money(automated.eligible_80g_deduction)],
                ["Tax after donation", money(automated.old_after_donation.total_tax)],
                [
                    "Final balance payable after donation",
                    money(automated.old_after_donation.balance_payable),
                ],
                ["Tax reduction", money(automated.tax_reduction_from_donation)],
            ],
            colWidths=[105 * mm, 55 * mm],
        )
        comparison.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4a37")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#b8b3a6")),
            ("PADDING", (0, 0), (-1, -1), 7),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ]))
        story.extend([
            Spacer(1, 6 * mm),
            Paragraph("Before and after donation", styles["Heading2"]),
            comparison,
        ])
    story.extend([
        Spacer(1, 5 * mm),
        Paragraph(
            "Advisory workpaper only. Reconcile the official portal/utility, AIS, "
            "Form 26AS, Form 16, tax challans and supporting evidence before filing.",
            styles["BodyText"],
        ),
    ])
    doc.build(story)
    return output.getvalue()
