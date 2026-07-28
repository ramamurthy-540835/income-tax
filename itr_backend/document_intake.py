from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

@dataclass(frozen=True)
class Classification:
    category: str
    document_type: str
    renamed_filename: str
    confidence: float
    extracted_text: str


RULES = (
    ("form16", "Form_16", (r"\bform\s*(?:no\.?\s*)?16\b", r"certificate under section 203")),
    ("ais", "Annual_Information_Statement", (r"annual information statement", r"\bais\b.*income tax")),
    ("26as", "Form_26AS", (r"\bform\s*26as\b", r"tax credit statement")),
    ("tis", "Taxpayer_Information_Summary", (r"taxpayer information summary",)),
    ("demand", "Outstanding_Demand", (r"outstanding demand", r"notice of demand", r"\bsection\s*156\b")),
    ("notice", "Income_Tax_Notice_139_9", (r"section\s*139\s*\(\s*9\s*\)", r"defective return")),
    ("notice", "Income_Tax_Notice_143_1", (r"section\s*143\s*\(\s*1", r"prima facie adjustment")),
    ("notice", "Income_Tax_Notice_142_1", (r"section\s*142\s*\(\s*1",)),
    ("notice", "Income_Tax_Notice_143_2", (r"section\s*143\s*\(\s*2",)),
    ("notice", "Income_Tax_Notice_144", (r"section\s*144\b", r"best judgment")),
    ("notice", "Income_Tax_Notice_148", (r"section\s*148a?\b", r"reassessment")),
    ("notice", "Income_Tax_Notice_245", (r"section\s*245\b", r"adjustment against demand")),
    ("notice", "Income_Tax_Notice_277A", (r"section\s*277a\b", r"falsification of books")),
    ("deduction_80g", "Donation_Receipt_80G", (r"\b80g\b", r"donation receipt")),
    ("deduction_80d", "Health_Insurance_80D", (r"\b80d\b", r"health insurance")),
    ("deduction_80c", "Investment_or_Premium_80C", (r"\b80c\b", r"life insurance premium", r"provident fund")),
    ("bank", "Bank_Statement", (r"bank statement", r"account statement")),
    ("identity", "Identity_Document", (r"income tax department.*permanent account number", r"\baadhaar\b")),
)


def safe_component(value: str) -> str:
    value = value.strip().replace("&", " and ")
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_-")


def _pdf_text(content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)[:50000]
    except Exception:
        return ""


def classify_document(
    content: bytes,
    original_filename: str,
    client_label: str,
    mime_type: str,
) -> Classification:
    text = _pdf_text(content) if mime_type == "application/pdf" else ""
    haystack = f"{original_filename}\n{text}".lower()
    category, title, confidence = "other", "Unclassified_Document", 0.35
    for candidate_category, candidate_title, patterns in RULES:
        if any(re.search(pattern, haystack, re.I | re.S) for pattern in patterns):
            category, title, confidence = candidate_category, candidate_title, 0.9
            break
    ay_match = re.search(r"(?:assessment\s+year|ay)\s*[:\-]?\s*(20\d{2})\s*[-–/]\s*(\d{2,4})", haystack, re.I)
    fy_match = re.search(r"(?:financial\s+year|fy)\s*[:\-]?\s*(20\d{2})\s*[-–/]\s*(\d{2,4})", haystack, re.I)
    year = ""
    match = ay_match or fy_match
    if match:
        year = f"{match.group(1)}-{match.group(2)[-2:]}"
    extension = Path(original_filename).suffix.lower()
    if extension not in {".pdf", ".jpg", ".jpeg", ".png"}:
        extension = ".pdf" if mime_type == "application/pdf" else ".bin"
    parts = [safe_component(client_label), title, year]
    stem = "_".join(part for part in parts if part)[:140].rstrip("_-")
    return Classification(
        category=category,
        document_type=title.replace("_", " "),
        renamed_filename=(stem or "Unclassified_Document") + extension,
        confidence=confidence,
        extracted_text=text,
    )
