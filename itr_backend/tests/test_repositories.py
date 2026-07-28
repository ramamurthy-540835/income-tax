from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from itr_backend.models import CustomerRecord
from itr_backend.repositories import GCSWorkspaceRepository
from itr_backend.service import generate_customer_id


class FakeBlob:
    def __init__(self, name: str):
        self.name = name
        self.data: str | None = None
        self.content_type: str | None = None
        self.if_generation_match: int | None = None
        self.deleted = False

    def upload_from_string(
        self,
        data: str,
        content_type: str,
        if_generation_match: int,
    ) -> None:
        self.data = data
        self.content_type = content_type
        self.if_generation_match = if_generation_match

    def delete(self) -> None:
        self.deleted = True


class FakeBucket:
    def __init__(self):
        self.blobs: dict[str, FakeBlob] = {}

    def blob(self, name: str) -> FakeBlob:
        blob = self.blobs.setdefault(name, FakeBlob(name))
        return blob

    def list_blobs(self, prefix: str):
        return [blob for name, blob in self.blobs.items() if name.startswith(prefix)]


class GCSWorkspaceRepositoryTests(unittest.TestCase):
    def test_initializes_complete_workspace_without_pii_in_prefix(self):
        bucket = FakeBucket()
        repository = GCSWorkspaceRepository(bucket)
        now = datetime.now(timezone.utc)
        customer = CustomerRecord(
            customer_id="cus_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            assessment_year="AY_2026-27",
            display_name="Sensitive Customer Name",
            preferred_regime="compare",
            status="provisioning",
            workspace_prefix=(
                "assessment-years/AY_2026-27/customers/"
                "cus_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"
            ),
            created_at=now,
            updated_at=now,
        )

        repository.initialize(customer)

        self.assertEqual(len(bucket.blobs), 9)
        prefix = customer.workspace_prefix
        self.assertIn(prefix + "01_source/originals/manifest.json", bucket.blobs)
        self.assertIn(prefix + "02_extracted/renamed/manifest.json", bucket.blobs)
        self.assertIn(prefix + "06_notices/manifest.json", bucket.blobs)
        self.assertIn(prefix + "07_reports/manifest.json", bucket.blobs)
        self.assertTrue(
            all("Sensitive" not in object_name for object_name in bucket.blobs)
        )
        self.assertTrue(
            all(blob.if_generation_match == 0 for blob in bucket.blobs.values())
        )
        profile_name = f"{customer.workspace_prefix}02_extracted/client_profile.json"
        profile = json.loads(bucket.blobs[profile_name].data or "{}")
        self.assertEqual(len(profile["eligibility"]), 11)

    def test_generated_customer_id_has_expected_shape(self):
        first = generate_customer_id()
        second = generate_customer_id()

        self.assertRegex(first, r"^cus_[0-9a-f]{32}$")
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
