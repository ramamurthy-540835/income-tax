#!/usr/bin/env python3
"""Extract reviewable ITR facts from a folder of PDFs using Gemini."""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
from typing import Any

import pdfplumber
from dotenv import dotenv_values
from google import genai
from google.genai import types
from pypdf import PdfReader, PdfWriter


PROMPT = """
You are extracting evidence for an Indian ITR-1 workpaper for FY 2025-26
(AY 2026-27). Read the supplied document carefully. Return exactly one JSON
object with:
document_type, issuer, financial_year, assessment_year, document_date,
is_relevant_to_fy_2025_26, taxpayer_name, evidence_quality,
income_items, tax_paid_items, deduction_items, identifiers, notes.

income_items entries: label, amount, head, source_page.
tax_paid_items entries: label, amount, kind (tds_salary, tds_other, tcs,
advance_tax, self_assessment_tax), source_page.
deduction_items entries: label, amount_paid, eligible_amount_if_explicit,
section (80C, 80CCD1B, 80CCD2, 80D, 80G, 80TTA, 80TTB, other, unknown),
payment_date, source_page, eligibility_notes.
identifiers may include masked values only. Do not return full PAN, Aadhaar,
bank account, policy number, address, phone, or email.

Never infer an amount not printed. For Form 16, distinguish gross salary,
exempt allowances, standard deduction, professional tax, Chapter VI-A
deductions, taxable income, tax deducted, and tax payable. For AIS, do not add
duplicate summary and transaction rows; identify aggregate values. School fees
qualify under 80C only for the tuition-fee component, for up to two children,
and only when paid in FY 2025-26. Insurance evidence must identify whether it is
life insurance (80C) or health insurance (80D). A policy schedule without proof
of payment is not payment evidence. Use null or an empty list when unsupported.
""".strip()


def _json_object(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Gemini did not return a JSON object")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Gemini response was not an object")
    return value


def _document_bytes(path: Path, passwords: list[str]) -> bytes:
    if path.suffix.lower() != ".pdf":
        return path.read_bytes()
    reader = PdfReader(path)
    if not reader.is_encrypted:
        return path.read_bytes()
    for password in passwords:
        try:
            if reader.decrypt(password):
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                output = io.BytesIO()
                writer.write(output)
                return output.getvalue()
        except Exception:
            continue
    raise ValueError(f"could not decrypt {path.name}")


def _local_text(path: Path, passwords: list[str]) -> str:
    if path.suffix.lower() != ".pdf":
        return ""
    password = passwords[0] if passwords else None
    try:
        with pdfplumber.open(path, password=password) as pdf:
            return "\n\n".join((page.extract_text() or "") for page in pdf.pages)[
                :40000
            ]
    except Exception:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    args = parser.parse_args()

    secrets = dotenv_values(args.env_file)
    api_key = (
        secrets.get("GEMINI_API_KEY")
        or secrets.get("GEMINI_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GEMINI_KEY")
    )
    if not api_key:
        raise ValueError("Gemini API key is missing")
    passwords = [
        str(value)
        for key, value in secrets.items()
        if value and "PASSWORD" in key.upper()
    ]
    client = genai.Client(api_key=str(api_key))
    results: list[dict[str, Any]] = []

    paths = [
        path
        for path in args.folder.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png"}
    ]
    for path in sorted(paths):
        print(f"Extracting {path.name} ...", flush=True)
        try:
            response = client.models.generate_content(
                model=args.model,
                contents=[
                    types.Part.from_bytes(
                        data=_document_bytes(path, passwords),
                        mime_type=(
                            "application/pdf"
                            if path.suffix.lower() == ".pdf"
                            else "image/jpeg"
                            if path.suffix.lower() in {".jpg", ".jpeg"}
                            else "image/png"
                        ),
                    ),
                    PROMPT
                    + "\n\nLocally extracted text (may be empty or incomplete):\n"
                    + (_local_text(path, passwords) or "[image-only document]"),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            result = _json_object(response.text)
            result["source_file"] = path.name
            result["status"] = "extracted"
        except Exception as exc:
            result = {
                "source_file": path.name,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(result)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"documents": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(results)} document results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
