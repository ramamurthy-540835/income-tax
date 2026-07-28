#!/usr/bin/env python3
"""Generate a reusable fillable Section 80G donation receipt template."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


TRUST_NAME = "NATURE LABS"
TRUST_PAN = "AACTN4446K"
TRUST_ADDRESS = (
    "No. 43, Mahalakshmi Nagar, IOB Colony, Bharathiyar University Post, "
    "Vadavalli, Coimbatore, Tamil Nadu 641046"
)
APPROVAL_NUMBER = "CIT(EXEMPTION), CHENNAI/80G/2020-21/A/10172"
APPROVAL_DATE = "20/07/2020"
SIGNATORY = "V Prakash, Managing Trustee"


def field(form, name, x, y, width, height=18, multiline=False):
    flags = 4096 if multiline else 0
    form.textfield(
        name=name,
        x=x,
        y=y,
        width=width,
        height=height,
        borderColor=colors.HexColor("#78909C"),
        fillColor=colors.white,
        textColor=colors.black,
        borderWidth=0.7,
        forceBorder=True,
        fontName="Helvetica",
        fontSize=9,
        fieldFlags=flags,
    )


def label(c, text, x, y, size=8.5, bold=False):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.setFillColor(colors.HexColor("#263238"))
    c.drawString(x, y, text)


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

    c.setTitle("Nature Labs Section 80G Donation Receipt Template")
    c.drawImage(
        ImageReader(str(args.logo)),
        42,
        height - 104,
        width=330,
        height=45,
        preserveAspectRatio=True,
        mask="auto",
        anchor="w",
    )
    c.setStrokeColor(green)
    c.setLineWidth(2)
    c.line(42, height - 112, width - 42, height - 112)

    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 139, "SECTION 80G DONATION RECEIPT")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.black)
    c.drawCentredString(
        width / 2,
        height - 154,
        "Reusable template · Issue only after actual receipt of donation",
    )

    y = height - 184
    label(c, "Receipt No.", 42, y, bold=True)
    field(form, "receipt_number", 110, y - 5, 150)
    label(c, "Pre-ARN (if applicable)", 300, y, bold=True)
    field(form, "pre_arn", 420, y - 5, 133)
    y -= 31
    label(c, "Donation date", 42, y, bold=True)
    field(form, "donation_date", 110, y - 5, 150)
    label(c, "Financial year", 300, y, bold=True)
    field(form, "financial_year", 420, y - 5, 133)

    y -= 34
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, y, "Donor particulars")
    y -= 25
    label(c, "Donor full name", 42, y, bold=True)
    field(form, "donor_name", 145, y - 5, 408)
    y -= 31
    label(c, "Donor PAN / ID", 42, y, bold=True)
    field(form, "donor_id", 145, y - 5, 190)
    label(c, "ID type", 355, y, bold=True)
    field(form, "donor_id_type", 405, y - 5, 148)
    y -= 31
    label(c, "Donor address", 42, y, bold=True)
    field(form, "donor_address", 145, y - 24, 408, 38, multiline=True)

    y -= 55
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, y, "Donation particulars")
    y -= 25
    label(c, "Amount (figures)", 42, y, bold=True)
    field(form, "amount_figures", 145, y - 5, 160)
    label(c, "Currency", 325, y, bold=True)
    field(form, "currency", 380, y - 5, 75)
    label(c, "INR", 467, y)
    y -= 31
    label(c, "Amount (words)", 42, y, bold=True)
    field(form, "amount_words", 145, y - 5, 408)
    y -= 31
    label(c, "Donation type", 42, y, bold=True)
    field(form, "donation_type", 145, y - 5, 160)
    label(c, "Corpus / Specific grant / Others", 315, y, size=7.5)
    y -= 31
    label(c, "Purpose / grant", 42, y, bold=True)
    field(form, "purpose", 145, y - 5, 408)
    y -= 31
    label(c, "Payment mode", 42, y, bold=True)
    field(form, "payment_mode", 145, y - 5, 160)
    label(c, "Non-cash required above Rs 2,000", 315, y, size=7.5)
    y -= 31
    label(c, "Transaction / cheque reference", 42, y, bold=True)
    field(form, "transaction_reference", 190, y - 5, 363)
    y -= 31
    label(c, "Bank / payment provider", 42, y, bold=True)
    field(form, "payment_provider", 170, y - 5, 190)
    label(c, "IFSC", 380, y, bold=True)
    field(form, "ifsc", 415, y - 5, 138)

    y -= 28
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, y, "Trust and approval particulars")
    y -= 19
    details_top = y
    label(c, "Donee", 42, y, size=7.5, bold=True)
    label(c, TRUST_NAME, 133, y, size=7.5)
    y -= 11
    label(c, "Registered address", 42, y, size=7.5, bold=True)
    label(
        c,
        "No. 43, Mahalakshmi Nagar, IOB Colony,",
        133,
        y,
        size=7.1,
    )
    y -= 10
    label(c, "Bharathiyar University Post, Vadavalli,", 133, y, size=7.1)
    y -= 10
    label(c, "Coimbatore, Tamil Nadu 641046", 133, y, size=7.1)
    y -= 11
    label(c, "PAN", 42, y, size=7.5, bold=True)
    label(c, TRUST_PAN, 133, y, size=7.5)
    y -= 11
    label(c, "80G approval", 42, y, size=7.5, bold=True)
    label(c, "CIT(EXEMPTION), CHENNAI/80G/", 133, y, size=7.2)
    y -= 10
    label(c, "2020-21/A/10172", 133, y, size=7.2)
    y -= 11
    label(c, "Approval date", 42, y, size=7.5, bold=True)
    label(c, APPROVAL_DATE, 133, y, size=7.5)
    y -= 11
    label(c, "Approval validity", 42, y, size=7.5, bold=True)
    label(
        c,
        "From AY 2020-21 until rescinded; verify current registration/URN",
        133,
        y,
        size=7.1,
    )
    y -= 11
    label(c, "Deduction category", 42, y, size=7.5, bold=True)
    label(
        c,
        "50% subject to qualifying limit; confirm against current Form 10BE",
        133,
        y,
        size=7.1,
    )

    # Keep the signature block inside the printable page.
    label(c, "For NATURE LABS", 400, details_top, bold=True)
    c.line(395, details_top - 35, 550, details_top - 35)
    label(c, SIGNATORY, 400, details_top - 49, size=8)
    label(c, "Authorized signature and seal", 400, details_top - 61, size=7.5)

    c.setFillColor(colors.HexColor("#F1F8E9"))
    c.roundRect(42, 20, width - 84, 52, 4, fill=1, stroke=0)
    c.setFillColor(colors.black)
    text = c.beginText(50, 61)
    text.setFont("Helvetica", 7.5)
    text.setLeading(10)
    text.textLine(
        "Certified that the donation described above was received voluntarily and "
        "without provision of goods or services in return."
    )
    text.textLine(
        "This receipt is not Form 10BE. The trust must report the donation in Form "
        "10BD and provide the portal-generated Form 10BE."
    )
    text.textLine(
        "Section 80G deduction is available only where legally eligible under the "
        "old tax regime; it is not claimable under the new regime."
    )
    text.textLine(
        "Approval, URN, deduction category, donor identity and payment evidence "
        "must be verified before issue."
    )
    c.drawText(text)

    c.setFont("Helvetica", 6.8)
    c.setFillColor(colors.HexColor("#455A64"))
    c.drawString(
        42,
        8,
        "Template control: verify current 80G registration/URN and authorized signatory before operational use.",
    )
    c.save()
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
