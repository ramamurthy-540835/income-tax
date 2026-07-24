from __future__ import annotations

import unittest

from itr_backend.tax_years import get_tax_year


class OfficialPortalSchemaTests(unittest.TestCase):
    def test_official_v11_schema_loads_with_bom_and_rejects_empty_payload(self):
        policy = get_tax_year("AY_2026-27")

        result = policy.validate_portal_payload({})

        self.assertFalse(result.valid)
        self.assertEqual(result.schema_version, "1.1")
        self.assertGreater(len(result.errors), 0)
        self.assertEqual(len(result.payload_sha256), 64)


if __name__ == "__main__":
    unittest.main()
