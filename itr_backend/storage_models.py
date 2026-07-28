from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentCategory = Literal[
    "ais",
    "form16",
    "26as",
    "tis",
    "bank",
    "deduction_80c",
    "deduction_80d",
    "deduction_80g",
    "house_property",
    "capital_gains",
    "notice",
    "demand",
    "identity",
    "other",
]


class StoredArtifact(BaseModel):
    object_name: str
    generation: int
    sha256: str
    size_bytes: int
    content_type: str
    updated_at: datetime


class DocumentRecord(BaseModel):
    document_id: str
    customer_id: str
    assessment_year: str
    category: DocumentCategory
    original_filename: str
    renamed_filename: str | None = None
    detected_document_type: str | None = None
    classification_confidence: float | None = Field(default=None, ge=0, le=1)
    object_name: str
    processing_object_name: str | None = None
    generation: int
    sha256: str
    size_bytes: int
    page_count: int
    status: Literal[
        "uploaded", "classified", "review_required", "verified", "rejected"
    ] = "uploaded"
    uploaded_at: datetime
    uploaded_by: str


class DocumentList(BaseModel):
    documents: list[DocumentRecord]


class BatchDocumentUploadResult(BaseModel):
    documents: list[DocumentRecord]
    failed: list[dict[str, str]] = Field(default_factory=list)


class FilingState(BaseModel):
    customer_id: str
    assessment_year: str
    status: Literal[
        "draft",
        "documents_pending",
        "review_pending",
        "ready_for_portal",
        "filed",
        "verified",
    ] = "draft"
    profile_generation: int | None = None
    return_data_generation: int | None = None
    portal_draft_generation: int | None = None
    validation_generation: int | None = None
    calculation_generation: int | None = None
    review_generation: int | None = None
    filing_evidence_generation: int | None = None
    schema_valid: bool = False
    preparer_approved: bool = False
    portal_validation_completed: bool = False
    created_at: datetime
    updated_at: datetime


class ArtifactWriteResult(BaseModel):
    artifact: StoredArtifact


class ConcurrencyToken(BaseModel):
    generation: int | None = Field(
        default=None,
        description="Expected current GCS generation; omit only for first creation.",
    )
