#!/usr/bin/env python3
"""Generate a fillable post-payment Section 80G donation receipt."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from itr_agent.generate_80g_receipt_template import (
    APPROVAL_DATE,
    APPROVAL_NUMBER,
    SIGNATORY,
    TRUST_NAME,
    TRUST_PAN,
    field,
    label,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(args.output), pagesize=A4)
    width, height = A4
    form = c.acroForm
    navy = colors.HexColor("#173F5F")
    green = colors.HexColor("#248A57")

    c.setTitle("Nature Labs Post-Donation Section 80G Receipt")
    c.drawImage(
        ImageReader(str(args.logo)),
        42,
        height - 104,
        width=330,
        height=45,
        mask="auto",
    )
    c.setStrokeColor(green)
    c.setLineWidth(2)
    c.line(42, height - 112, width - 42, height - 112)
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(width / 2, height - 138, "80G DONATION RECEIPT")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(green)
    c.drawCentredString(
        width / 2,
        height - 153,
        "PAYMENT RECEIVED · POST-DONATION ACKNOWLEDGEMENT",
    )

    y = height - 183
    label(c, "Receipt No.", 42, y, bold=True)
    field(form, "receipt_number", 110, y - 5, 150)
    label(c, "Pre-ARN", 300, y, bold=True)
    field(form, "pre_arn", 365, y - 5, 188)
    y -= 27
    label(c, "Receipt issue date", 42, y, bold=True)
    field(form, "receipt_issue_date", 140, y - 5, 120)
    label(c, "Financial year", 300, y, bold=True)
    field(form, "financial_year", 390, y - 5, 163)

    y -= 28
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, y, "Donor particulars")
    y -= 24
    label(c, "Donor full name", 42, y, bold=True)
    field(form, "donor_name", 145, y - 5, 408)
    y -= 27
    label(c, "Donor PAN / ID", 42, y, bold=True)
    field(form, "donor_id", 145, y - 5, 190)
    label(c, "ID type", 355, y, bold=True)
    field(form, "donor_id_type", 405, y - 5, 148)
    y -= 27
    label(c, "Donor address", 42, y, bold=True)
    field(form, "donor_address", 145, y - 22, 408, 36, multiline=True)

    y -= 51
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, y, "Payment received")
    y -= 24
    label(c, "Amount received", 42, y, bold=True)
    field(form, "amount_received", 145, y - 5, 160)
    label(c, "Amount in words", 325, y, bold=True)
    field(form, "amount_words", 415, y - 5, 138)
    y -= 27
    label(c, "Donation date", 42, y, bold=True)
    field(form, "donation_date", 145, y - 5, 160)
    label(c, "Value date", 325, y, bold=True)
    field(form, "value_date", 415, y - 5, 138)
    y -= 27
    label(c, "Donation type", 42, y, bold=True)
    field(form, "donation_type", 145, y - 5, 160)
    label(c, "Corpus / Specific grant / Others", 315, y, size=7.5)
    y -= 27
    label(c, "Purpose / grant", 42, y, bold=True)
    field(form, "purpose", 145, y - 5, 408)
    y -= 27
    label(c, "Payment mode", 42, y, bold=True)
    field(form, "payment_mode", 145, y - 5, 160)
    label(c, "Electronic / Cheque / Draft / Cash / Other", 315, y, size=7.5)
    y -= 27
    label(c, "Transaction / cheque reference", 42, y, bold=True)
    field(form, "transaction_reference", 190, y - 5, 363)
    y -= 27
    label(c, "Remitting bank / provider", 42, y, bold=True)
    field(form, "payment_provider", 175, y - 5, 180)
    label(c, "IFSC", 375, y, bold=True)
    field(form, "ifsc", 410, y - 5, 143)

    y -= 28
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, y, "Verification and certificate status")
    y -= 24
    form.checkbox(
        name="payment_verified",
        x=42,
        y=y - 4,
        buttonStyle="check",
        borderColor=colors.HexColor("#78909C"),
        fillColor=colors.white,
        size=12,
    )
    label(c, "Funds received and transaction verified", 61, y, size=8.2)
    form.checkbox(
        name="form10bd_reported",
        x=285,
        y=y - 4,
        buttonStyle="check",
        borderColor=colors.HexColor("#78909C"),
        fillColor=colors.white,
        size=12,
    )
    label(c, "Included in Form 10BD", 304, y, size=8.2)
    y -= 25
    label(c, "Form 10BE certificate No./ARN", 42, y, bold=True)
    field(form, "form10be_reference", 200, y - 5, 170)
    label(c, "Issue date", 390, y, bold=True)
    field(form, "form10be_issue_date", 445, y - 5, 108)

    y -= 28
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, y, "Trust and 80G particulars")
    y -= 17
    trust_rows = [
        ("Donee", TRUST_NAME),
        ("PAN", TRUST_PAN),
        ("Address", "No. 43, Mahalakshmi Nagar, IOB Colony, Bharathiyar University Post,"),
        ("", "Vadavalli, Coimbatore, Tamil Nadu 641046"),
        ("80G approval", APPROVAL_NUMBER),
        ("Approval date", APPROVAL_DATE),
        ("Category", "50% subject to qualifying limit; verify current approval and Form 10BE"),
    ]
    for key, value in trust_rows:
        label(c, key, 42, y, size=7.2, bold=bool(key))
        label(c, value, 125, y, size=7.1)
        y -= 10

    label(c, "For NATURE LABS", 400, y + 60, bold=True)
    c.line(395, y + 28, 550, y + 28)
    label(c, SIGNATORY, 400, y + 15, size=8)
    label(c, "Authorized signature and seal", 400, y + 3, size=7.2)

    c.setFillColor(colors.HexColor("#F1F8E9"))
    c.roundRect(42, 27, width - 84, 52, 4, fill=1, stroke=0)
    c.setFillColor(colors.black)
    text = c.beginText(50, 67)
    text.setFont("Helvetica", 7.3)
    text.setLeading(9.5)
    text.textLine(
        "Nature Labs acknowledges actual receipt of the donation stated above, "
        "subject to payment realization and verification."
    )
    text.textLine(
        "This receipt does not replace Form 10BE. Deduction requires matching "
        "Form 10BD reporting and the portal-generated Form 10BE."
    )
    text.textLine(
        "80G deduction is available only where legally eligible under the old "
        "tax regime; it is not claimable under the new regime."
    )
    text.textLine(
        "Cash donations above Rs 2,000 are not deductible under Section 80G."
    )
    c.drawText(text)
    c.setFont("Helvetica", 6.7)
    c.setFillColor(colors.HexColor("#455A64"))
    c.drawString(
        42,
        13,
        "Issue only after funds clear and current 80G registration/URN, category and signatory authority are verified.",
    )
    c.save()
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
