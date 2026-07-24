from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Protocol

from google.api_core.exceptions import Conflict, NotFound, PreconditionFailed
from google.cloud import firestore, storage

from itr_backend.storage_models import (
    DocumentRecord,
    FilingState,
    StoredArtifact,
)


class FilingStateNotFoundError(Exception):
    pass


class ArtifactNotFoundError(Exception):
    pass


class ConcurrentUpdateError(Exception):
    pass


class FilingMetadataRepository(Protocol):
    def workspace_exists(self, assessment_year: str, customer_id: str) -> bool: ...

    def create_state(self, state: FilingState) -> None: ...

    def get_state(self, assessment_year: str, customer_id: str) -> FilingState: ...

    def update_state(
        self, assessment_year: str, customer_id: str, updates: dict[str, Any]
    ) -> FilingState: ...

    def create_document(self, document: DocumentRecord) -> None: ...

    def list_documents(
        self, assessment_year: str, customer_id: str
    ) -> list[DocumentRecord]: ...


class ArtifactRepository(Protocol):
    def read_json(self, object_name: str) -> tuple[dict[str, Any], int]: ...

    def write_json(
        self,
        object_name: str,
        payload: dict[str, Any],
        expected_generation: int | None,
    ) -> StoredArtifact: ...

    def write_bytes(
        self,
        object_name: str,
        payload: bytes,
        content_type: str,
    ) -> StoredArtifact: ...

    def read_bytes(self, object_name: str) -> tuple[bytes, str, int]: ...


class FirestoreFilingMetadataRepository:
    def __init__(self, client: firestore.Client):
        self._client = client

    def _customer_ref(self, assessment_year: str, customer_id: str):
        return (
            self._client.collection("assessment_years")
            .document(assessment_year)
            .collection("customers")
            .document(customer_id)
        )

    def _state_ref(self, assessment_year: str, customer_id: str):
        return (
            self._customer_ref(assessment_year, customer_id)
            .collection("filing_state")
            .document("current")
        )

    def _documents(self, assessment_year: str, customer_id: str):
        return self._customer_ref(assessment_year, customer_id).collection("documents")

    def workspace_exists(self, assessment_year: str, customer_id: str) -> bool:
        return self._customer_ref(assessment_year, customer_id).get().exists

    def create_state(self, state: FilingState) -> None:
        try:
            self._state_ref(state.assessment_year, state.customer_id).create(
                state.model_dump(mode="python")
            )
        except Conflict as exc:
            raise ConcurrentUpdateError("filing state already exists") from exc

    def get_state(self, assessment_year: str, customer_id: str) -> FilingState:
        snapshot = self._state_ref(assessment_year, customer_id).get()
        if not snapshot.exists:
            raise FilingStateNotFoundError(customer_id)
        return FilingState.model_validate(snapshot.to_dict())

    def update_state(
        self, assessment_year: str, customer_id: str, updates: dict[str, Any]
    ) -> FilingState:
        updates = {**updates, "updated_at": firestore.SERVER_TIMESTAMP}
        reference = self._state_ref(assessment_year, customer_id)
        try:
            reference.update(updates)
        except NotFound as exc:
            raise FilingStateNotFoundError(customer_id) from exc
        return self.get_state(assessment_year, customer_id)

    def create_document(self, document: DocumentRecord) -> None:
        try:
            self._documents(document.assessment_year, document.customer_id).document(
                document.document_id
            ).create(document.model_dump(mode="python"))
        except Conflict as exc:
            raise ConcurrentUpdateError(document.document_id) from exc

    def list_documents(
        self, assessment_year: str, customer_id: str
    ) -> list[DocumentRecord]:
        query = self._documents(assessment_year, customer_id).order_by(
            "uploaded_at", direction=firestore.Query.DESCENDING
        )
        return [
            DocumentRecord.model_validate(snapshot.to_dict())
            for snapshot in query.stream()
        ]


class GCSArtifactRepository:
    def __init__(self, bucket: storage.Bucket):
        self._bucket = bucket

    @staticmethod
    def _artifact(blob: storage.Blob, payload: bytes) -> StoredArtifact:
        return StoredArtifact(
            object_name=blob.name,
            generation=int(blob.generation),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            content_type=blob.content_type or "application/octet-stream",
            updated_at=datetime.now(timezone.utc),
        )

    def read_json(self, object_name: str) -> tuple[dict[str, Any], int]:
        payload, _, generation = self.read_bytes(object_name)
        return json.loads(payload.decode("utf-8-sig")), generation

    def write_json(
        self,
        object_name: str,
        payload: dict[str, Any],
        expected_generation: int | None,
    ) -> StoredArtifact:
        encoded = (
            json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n"
        ).encode("utf-8")
        blob = self._bucket.blob(object_name)
        precondition = 0 if expected_generation is None else expected_generation
        try:
            blob.upload_from_string(
                encoded,
                content_type="application/json",
                if_generation_match=precondition,
            )
        except PreconditionFailed as exc:
            raise ConcurrentUpdateError(object_name) from exc
        return self._artifact(blob, encoded)

    def write_bytes(
        self,
        object_name: str,
        payload: bytes,
        content_type: str,
    ) -> StoredArtifact:
        blob = self._bucket.blob(object_name)
        try:
            blob.upload_from_string(
                payload,
                content_type=content_type,
                if_generation_match=0,
            )
        except PreconditionFailed as exc:
            raise ConcurrentUpdateError(object_name) from exc
        return self._artifact(blob, payload)

    def read_bytes(self, object_name: str) -> tuple[bytes, str, int]:
        blob = self._bucket.blob(object_name)
        try:
            payload = blob.download_as_bytes()
            blob.reload()
        except NotFound as exc:
            raise ArtifactNotFoundError(object_name) from exc
        return (
            payload,
            blob.content_type or "application/octet-stream",
            int(blob.generation),
        )
