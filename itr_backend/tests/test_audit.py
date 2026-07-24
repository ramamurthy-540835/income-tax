from __future__ import annotations

import io
import unittest

from pypdf import PdfWriter

from itr_backend.audit import AuditEvent
from itr_backend.filing_service import FilingService
from itr_backend.tests.test_filing_service import (
    AY,
    CUSTOMER_ID,
    PREFIX,
    InMemoryArtifacts,
    InMemoryMetadata,
    complete_profile,
)


class CapturingAuditRepository:
    def __init__(self):
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)


class FilingAuditTests(unittest.TestCase):
    def setUp(self):
        self.metadata = InMemoryMetadata()
        self.artifacts = InMemoryArtifacts()
        self.audit = CapturingAuditRepository()
        self.service = FilingService(
            self.metadata,
            self.artifacts,
            audit=self.audit,
        )

    def test_profile_audit_records_actor_without_taxpayer_payload(self):
        self.service.put_profile(
            AY,
            CUSTOMER_ID,
            complete_profile(),
            None,
            "google-subject-1",
        )

        event = self.audit.events[-1]
        self.assertEqual(event.action, "profile.updated")
        self.assertEqual(event.actor, "google-subject-1")
        self.assertEqual(event.details, {"generation": 1})
        self.assertNotIn("pan", str(event.details).lower())

    def test_document_uses_single_workspace_prefix_and_is_audited(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = io.BytesIO()
        writer.write(output)

        document = self.service.upload_document(
            AY,
            CUSTOMER_ID,
            "form16",
            "Form 16.pdf",
            output.getvalue(),
            "google-subject-2",
        )

        self.assertTrue(document.object_name.startswith(PREFIX + "01_source/"))
        self.assertEqual(document.object_name.count(PREFIX), 1)
        event = self.audit.events[-1]
        self.assertEqual(event.action, "document.uploaded")
        self.assertEqual(event.details["sha256"], document.sha256)


if __name__ == "__main__":
    unittest.main()
