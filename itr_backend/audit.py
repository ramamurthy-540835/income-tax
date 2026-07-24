from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from google.cloud import firestore
from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    event_id: str
    assessment_year: str
    customer_id: str
    action: str = Field(min_length=1, max_length=80)
    actor: str = Field(min_length=1, max_length=200)
    occurred_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...


class NoopAuditRepository:
    def append(self, event: AuditEvent) -> None:
        return None


class FirestoreAuditRepository:
    def __init__(self, client: firestore.Client):
        self._client = client

    def append(self, event: AuditEvent) -> None:
        reference = (
            self._client.collection("assessment_years")
            .document(event.assessment_year)
            .collection("customers")
            .document(event.customer_id)
            .collection("audit_events")
            .document(event.event_id)
        )
        reference.create(event.model_dump(mode="python"))


def new_audit_event(
    assessment_year: str,
    customer_id: str,
    action: str,
    actor: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        assessment_year=assessment_year,
        customer_id=customer_id,
        action=action,
        actor=actor,
        occurred_at=datetime.now(timezone.utc),
        details=details or {},
    )
