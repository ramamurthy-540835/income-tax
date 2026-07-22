#!/usr/bin/env python3
"""Preview-first AI agent for classifying and renaming arbitrary client PDFs.

The script sends each PDF to the OpenAI Responses API, asks the model to identify
the document, builds a conservative upload-safe filename, and writes an audit CSV.
Files are renamed only when --apply is supplied.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
MAX_FILENAME_LENGTH = 150

SYSTEM_PROMPT = """
You are a careful professional document-filing agent. Inspect the supplied PDF,
including scanned page images, and identify what it actually is. The client may
submit any document: tax, identity, insurance, banking, investment, property,
education, employment, medical, legal, invoice, receipt, certificate, statement,
or an unfamiliar type. Return exactly one JSON
object and no markdown.

Required keys:
  document_type: the most specific short factual title supported by the PDF
  person_or_student: name only when clearly printed, otherwise empty string
  issuer: short organization name, otherwise empty string
  financial_year: YYYY-YY when clearly supported, otherwise empty string
  assessment_year: YYYY-YY when clearly supported, otherwise empty string
  document_date: YYYY-MM-DD when clearly printed, otherwise empty string
  receipt_or_policy_number: useful receipt/policy/certificate number, otherwise
    empty string
  amount: digits and decimal point only, otherwise empty string
  confidence: number from 0 to 1
  notes: one short factual description; explain uncertainty if applicable
  proposed_filename: a concise filename ending in .pdf

Filename rules:
- Use only letters, digits, underscores, hyphens, and the final .pdf extension.
- Prefer: Person_Document_Type_Issuer_Year_Date_Reference.pdf.
- Include only fields that are genuinely useful and visible.
- Never include PAN, Aadhaar, bank account, phone, email, or street address.
- Do not invent missing values.
- Keep the filename under 140 characters.
- Use the document's own heading and context; never force it into a tax category.
""".strip()


@dataclass
class RenamePlan:
    source: Path
    destination: Path
    metadata: dict[str, Any]
    status: str = "planned"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze and safely rename tax-document PDFs. Dry-run is the default."
    )
    parser.add_argument("folder", nargs="?", default=".", help="Folder containing PDFs")
    parser.add_argument("--apply", action="store_true", help="Actually rename files")
    parser.add_argument("--recursive", action="store_true", help="Include subfolders")
    parser.add_argument("--client", default="", help="Optional client name prefix")
    parser.add_argument(
        "--provider", choices=("auto", "openai", "gemini"), default="auto",
        help="AI provider; auto uses an available API key",
    )
    parser.add_argument("--model", default="", help="Override the provider's model ID")
    parser.add_argument(
        "--detail", choices=("low", "high", "auto"), default="high",
        help="PDF page-image detail; high is best for scanned receipts",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.65,
        help="Do not rename below this confidence (default: 0.65)",
    )
    return parser.parse_args()


def safe_component(value: str) -> str:
    value = value.strip().replace("&", " and ")
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_-")


def safe_pdf_name(suggested: str, client_name: str = "") -> str:
    stem = Path(suggested).stem
    stem = safe_component(stem)
    prefix = safe_component(client_name)
    if prefix and not stem.lower().startswith(prefix.lower() + "_"):
        stem = f"{prefix}_{stem}"
    stem = stem[: MAX_FILENAME_LENGTH - 4].rstrip("_-")
    return (stem or "Unclassified_Tax_Document") + ".pdf"


def unique_destination(source: Path, requested_name: str, reserved: set[Path]) -> Path:
    candidate = source.with_name(requested_name)
    index = 2
    while (candidate.exists() and candidate != source) or candidate in reserved:
        candidate = source.with_name(f"{Path(requested_name).stem}_{index}.pdf")
        index += 1
    reserved.add(candidate)
    return candidate


def pdf_as_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/pdf"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return a JSON object")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Model response was not a JSON object")
    return value


def extract_local_text(path: Path, max_chars: int = 30000) -> str:
    """Use pdfplumber first; image-only PDFs simply return little or no text."""
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
            if sum(map(len, chunks)) >= max_chars:
                break
    return "\n\n".join(chunks)[:max_chars]


def analyze_openai(path: Path, model: str, detail: str, local_text: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    text_hint = local_text or "[No usable embedded text; rely on page vision/OCR.]"
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"Analyze this PDF. Current filename: {path.name!r}.\n"
                            f"Locally extracted text (may be incomplete):\n{text_hint}"
                        ),
                    },
                    {
                        "type": "input_file",
                        "filename": path.name,
                        "file_data": pdf_as_data_url(path),
                        "detail": detail,
                    },
                ],
            }
        ],
    )
    return extract_json(response.output_text)


def analyze_gemini(path: Path, model: str, local_text: str) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=gemini_api_key())
    text_hint = local_text or "[No usable embedded text; rely on page vision/OCR.]"
    prompt = (
        SYSTEM_PROMPT
        + f"\n\nCurrent filename: {path.name!r}.\n"
        + f"Locally extracted text (may be incomplete):\n{text_hint}"
    )
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=path.read_bytes(), mime_type="application/pdf"),
            prompt,
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return extract_json(response.text)


def choose_provider(requested: str) -> str:
    if requested != "auto":
        return requested
    if gemini_api_key():
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    raise RuntimeError("Set GEMINI_API_KEY or OPENAI_API_KEY")


def gemini_api_key() -> str:
    """Support Google's standard name and the shorter legacy/local alias."""
    return os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY") or ""


def analyze_pdf(path: Path, provider: str, model: str, detail: str) -> dict[str, Any]:
    local_text = extract_local_text(path)
    if provider == "gemini":
        return analyze_gemini(path, model, local_text)
    return analyze_openai(path, model, detail, local_text)


def discover_pdfs(folder: Path, recursive: bool) -> list[Path]:
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        (p for p in iterator if p.is_file() and p.suffix.lower() == ".pdf"),
        key=lambda p: str(p).lower(),
    )


def write_audit(folder: Path, plans: list[RenamePlan], applied: bool) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / f"rename_audit_{stamp}.csv"
    fields = [
        "source", "destination", "status", "document_type", "person_or_student",
        "issuer", "financial_year", "assessment_year", "document_date",
        "receipt_or_policy_number", "amount", "confidence", "notes",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for plan in plans:
            row = {key: plan.metadata.get(key, "") for key in fields}
            row.update(
                source=str(plan.source), destination=str(plan.destination),
                status=plan.status if applied else "dry-run",
            )
            writer.writerow(row)
    return path


def main() -> int:
    args = parse_args()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 2
    try:
        provider = choose_provider(args.provider)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    required_key = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
    key_is_present = gemini_api_key() if provider == "gemini" else os.getenv(required_key)
    if not key_is_present:
        print(f"Set {required_key} or choose another provider.", file=sys.stderr)
        return 2
    model = args.model or (
        DEFAULT_GEMINI_MODEL if provider == "gemini" else DEFAULT_OPENAI_MODEL
    )

    pdfs = discover_pdfs(folder, args.recursive)
    if not pdfs:
        print("No PDF files found.")
        return 0

    plans: list[RenamePlan] = []
    reserved: set[Path] = set()

    for number, pdf in enumerate(pdfs, 1):
        print(f"[{number}/{len(pdfs)}] Analyzing {pdf.name} ...", flush=True)
        try:
            metadata = analyze_pdf(pdf, provider, model, args.detail)
            confidence = float(metadata.get("confidence", 0))
            if confidence < args.min_confidence:
                plans.append(RenamePlan(pdf, pdf, metadata, "skipped_low_confidence"))
                print(f"  SKIP: confidence {confidence:.2f}")
                continue
            proposed = safe_pdf_name(str(metadata.get("proposed_filename", "")), args.client)
            destination = unique_destination(pdf, proposed, reserved)
            status = "unchanged" if destination == pdf else "planned"
            plans.append(RenamePlan(pdf, destination, metadata, status))
            print(f"  {pdf.name}  ->  {destination.name}  ({confidence:.2f})")
        except Exception as exc:  # Continue safely with the remaining client documents.
            plans.append(RenamePlan(pdf, pdf, {"notes": str(exc)}, "error"))
            print(f"  ERROR: {exc}", file=sys.stderr)

    actionable = [p for p in plans if p.status == "planned"]
    if args.apply:
        for plan in actionable:
            plan.source.rename(plan.destination)
            plan.status = "renamed"
        print(f"\nRenamed {len(actionable)} file(s).")
    else:
        print(f"\nDry run only: {len(actionable)} rename(s) proposed.")
        print("Review the plan, then run the same command with --apply.")

    audit = write_audit(folder, plans, args.apply)
    print(f"Audit log: {audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
