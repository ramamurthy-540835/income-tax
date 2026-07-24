from __future__ import annotations

import unittest

from itr_backend.filing_service import FilingService, FilingValidationError
from itr_backend.tests.test_filing_service import (
    AY,
    CUSTOMER_ID,
    InMemoryArtifacts,
    InMemoryMetadata,
)


class FilingIntegrityTests(unittest.TestCase):
    def test_orphan_filing_state_is_rejected(self):
        metadata = InMemoryMetadata()
        metadata.workspaces.clear()
        service = FilingService(metadata, InMemoryArtifacts())

        with self.assertRaises(FilingValidationError):
            service.ensure_state(AY, CUSTOMER_ID)


if __name__ == "__main__":
    unittest.main()
