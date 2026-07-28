from __future__ import annotations

import io
from datetime import date

from pypdf import PdfReader, PdfWriter


class PdfPasswordError(ValueError):
    pass


def ais_password(pan: str, date_of_birth: date) -> str:
    """Income-tax AIS PDFs use lower-case PAN followed by DOB as DDMMYYYY."""
    return f"{pan.strip().lower()}{date_of_birth:%d%m%Y}"


def unlock_ais_pdf(content: bytes, pan: str, date_of_birth: date) -> tuple[bytes, int]:
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
    except Exception as exc:
        raise PdfPasswordError("AIS PDF is malformed or unreadable") from exc
    if not reader.is_encrypted:
        return content, len(reader.pages)
    if reader.decrypt(ais_password(pan, date_of_birth)) == 0:
        raise PdfPasswordError(
            "AIS PDF could not be opened using lowercase PAN plus DOB (DDMMYYYY)"
        )
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), len(reader.pages)
