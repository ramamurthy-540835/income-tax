#!/usr/bin/env python3
"""Generate separate Zeno old/new regime advisory workpapers."""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from itr_agent.generate_itr_workpaper import rupees, table


D = Decimal


def round_rupee(value: Decimal) -> int:
    return int(value.quantize(D("1"), rounding=ROUND_HALF_UP))


def round_ten(value: Decimal) -> int:
    return int((value / D("10")).quantize(D("1"), rounding=ROUND_HALF_UP) * 10)


def slab_tax(income: Decimal, regime: str) -> Decimal:
    if regime == "old":
        slabs = [(D("250000"), D("0")), (D("500000"), D(".05")),
                 (D("1000000"), D(".20")), (None, D(".30"))]
    else:
        slabs = [(D("400000"), D("0")), (D("800000"), D(".05")),
                 (D("1200000"), D(".10")), (D("1600000"), D(".15")),
                 (D("2000000"), D(".20")), (D("2400000"), D(".25")),
                 (None, D(".30"))]
    tax = D("0")
    lower = D("0")
    for upper, rate in slabs:
        taxable = income - lower if upper is None else min(
            max(income - lower, 0), upper - lower
        )
        tax += max(taxable, 0) * rate
        if upper is None or income <= upper:
            break
        lower = upper
    return tax


def tax_result(total_income: Decimal, regime: str) -> dict[str, int]:
    rounded_income = D(round_ten(total_income))
    base = slab_tax(rounded_income, regime)
    surcharge = base * D(".10") if rounded_income > D("5000000") else D("0")
    if surcharge:
        threshold_tax = slab_tax(D("5000000"), regime)
        max_tax_with_surcharge = threshold_tax + rounded_income - D("5000000")
        surcharge = min(surcharge, max(max_tax_with_surcharge - base, D("0")))
    tax_after_surcharge = base + surcharge
    cess = tax_after_surcharge * D(".04")
    return {
        "total_income": int(rounded_income),
        "base_tax": round_rupee(base),
        "surcharge": round_rupee(surcharge),
        "cess": round_rupee(cess),
        "total_tax": round_ten(tax_after_surcharge + cess),
    }


def build(output: Path, regime: str) -> None:
    gross_salary = D("7165743")
    exempt_hra = D("77424")
    professional_tax = D("2500")
    savings_interest = D("14597")
    deposit_interest = D("1212310")
    dividend = D("1723")
    other_income = savings_interest + deposit_interest + dividend
    taxes_paid = 2_148_714 + 116_513 + 19_490

    if regime == "old":
        salary_income = gross_salary - exempt_hra - D("50000") - professional_tax
        gti = salary_income + other_income
        non_80g = D("150000") + D("10000")
        baseline_result = tax_result(gti - non_80g, regime)
        adjusted_gti = gti - non_80g
        donation_ceiling = D(round_rupee(adjusted_gti * D(".10")))
        donation = donation_ceiling
        deduction_80g = D(round_rupee(donation * D(".50")))
        total_deductions = non_80g + deduction_80g
        donation_result = tax_result(gti - total_deductions, regime)
    else:
        salary_income = gross_salary - D("75000")
        gti = salary_income + other_income
        adjusted_gti = donation_ceiling = donation = deduction_80g = D("0")
        total_deductions = D("0")
        baseline_result = tax_result(gti, regime)
        donation_result = baseline_result

    result = baseline_result
    balance = max(result["total_tax"] - taxes_paid, 0)
    refund = max(taxes_paid - result["total_tax"], 0)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleZeno", parent=styles["Title"], alignment=TA_CENTER,
        textColor=colors.HexColor("#153E5C"), fontSize=18, leading=22,
    )
    small = ParagraphStyle(
        "SmallZeno", parent=styles["BodyText"], fontSize=8.5, leading=11
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"Zeno {regime.title()} Regime Tax Workpaper",
    )
    story = [
        Paragraph(f"Zeno – {regime.title()} Regime Tax Calculation", title),
        Paragraph(
            "FY 2025-26 / AY 2026-27 · Generated "
            + datetime.now().strftime("%d %B %Y"),
            styles["Normal"],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Filing-form blocker", styles["Heading2"]),
        Paragraph(
            "<b>ITR-1 is not applicable.</b> Total income exceeds Rs 50 lakh. "
            "This workpaper is an advisory ITR-2 calculation and requires "
            "Schedule AL and current official-utility validation.",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Tax calculation", styles["Heading2"]),
        table(
            [
                ["Particular", "Amount"],
                ["Gross salary", rupees(int(gross_salary))],
                ["Taxable salary", rupees(round_rupee(salary_income))],
                ["Savings interest", rupees(int(savings_interest))],
                ["Deposit interest", rupees(int(deposit_interest))],
                ["Dividend income", rupees(int(dividend))],
                ["Gross total income", rupees(round_rupee(gti))],
                [
                    "Chapter VI-A deductions"
                    + (" (before donation)" if regime == "old" else ""),
                    rupees(round_rupee(non_80g if regime == "old" else total_deductions)),
                ],
                ["Total income (rounded)", rupees(result["total_income"])],
                ["Income tax before surcharge", rupees(result["base_tax"])],
                ["Surcharge", rupees(result["surcharge"])],
                ["Health & education cess", rupees(result["cess"])],
                [
                    "Total tax liability"
                    + (" before donation" if regime == "old" else ""),
                    rupees(result["total_tax"]),
                ],
                ["TDS and TCS credits", rupees(taxes_paid)],
                ["Balance payable", rupees(balance)],
                ["Refund", rupees(refund)],
            ],
            [92 * mm, 70 * mm],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Deduction particulars", styles["Heading2"]),
    ]
    evidence = [
        ("80C – Form 16 / PF-life insurance etc.", 150_000, "Form 16 claim; statutory cap reached"),
        ("80CCD(1B) – additional NPS", 0, "No separate evidence found"),
        ("80CCD(2) – employer NPS", 0, "No evidence found"),
        ("80D – health insurance", 0, "No receipt found"),
        ("80DD", 0, "No evidence found"),
        ("80DDB", 0, "No evidence found"),
        ("80E", 0, "No evidence found"),
        ("80EE / 80EEA", 0, "No evidence found"),
        ("80EEB", 0, "No evidence found"),
        ("80G", int(deduction_80g), "Planned; receipt/Form 10BE pending"),
        ("80GGA", 0, "No evidence found"),
        ("80GGC", 0, "No evidence found"),
        ("80TTA", 10_000, "AIS savings interest; statutory cap"),
        ("80TTB", 0, "Not applied"),
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
        story.extend(
            [
                Paragraph("Donation required under assumed 80G category", styles["Heading2"]),
                table(
                    [
                        ["Particular", "Amount / result"],
                        ["Target", "Bring final tax as close as legally possible to taxes paid"],
                        ["Assumed category", "50% deduction subject to 10% adjusted-GTI limit"],
                        ["Adjusted gross total income", rupees(round_rupee(adjusted_gti))],
                        ["Maximum qualifying donation pool", rupees(int(donation_ceiling))],
                        ["Recommended donation to pay", rupees(int(donation))],
                        ["Eligible deduction at 50%", rupees(int(deduction_80g))],
                        ["Total income after donation", rupees(donation_result["total_income"])],
                        ["Tax before donation", rupees(baseline_result["total_tax"])],
                        ["Tax after maximum eligible donation", rupees(donation_result["total_tax"])],
                        [
                            "Tax reduction from donation",
                            rupees(baseline_result["total_tax"] - donation_result["total_tax"]),
                        ],
                        ["Taxes already paid", rupees(taxes_paid)],
                        [
                            "Remaining payable after donation",
                            rupees(max(donation_result["total_tax"] - taxes_paid, 0)),
                        ],
                        [
                            "Refund after donation",
                            rupees(max(taxes_paid - donation_result["total_tax"], 0)),
                        ],
                        ["Status", "PLANNED / NOT YET EVIDENCED"],
                    ],
                    [72 * mm, 90 * mm],
                ),
                Spacer(1, 4 * mm),
                Paragraph(
                    "A larger payment in this limited category would not increase "
                    "the deduction. The target of matching taxes paid cannot be "
                    "reached through this assumed 80G category.",
                    styles["BodyText"],
                ),
            ]
        )
    else:
        story.extend(
            [
                Paragraph("Donation treatment", styles["Heading2"]),
                Paragraph(
                    "Section 80G is not deductible under the new regime. No donation "
                    "has been included in this calculation.",
                    styles["BodyText"],
                ),
            ]
        )
    story.extend(
        [
            Spacer(1, 4 * mm),
            Paragraph(
                "Advisory workpaper only. Confirm age/residency, Form 26AS/AIS "
                "feedback, assets and liabilities, bank accounts, all special-rate "
                "income, interest/fees, and portal-computed surcharge/marginal relief "
                "before filing ITR-2.",
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
            / f"ZENO_FY2025-26_{regime.upper()}_Regime_ITR2_Advisory.pdf",
            regime,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
