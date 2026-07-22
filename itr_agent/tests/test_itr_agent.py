import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "itr_agent" / "itr_filing_agent.py"


class FilingAgentIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.client = Path(self.temp.name) / "SYNTHETIC_CLIENT_AY_2026-27"
        self.run_agent("init", str(self.client), "--client-id", "SYNTHETIC", "--regime", "old")
        extracted = self.client / "02_extracted"
        (extracted / "return_data.json").write_text(json.dumps({
            "assessment_year": "2026-27",
            "financial_year": "2025-26",
            "taxpayer": {"age_band": "below_60"},
            "income": {"gross_salary": 2355971, "savings_interest": 4692,
                       "other_ordinary_income": 0, "special_rate_income": 0,
                       "business_income": 0},
            "tax_paid": {"tds": 281060},
            "deductions": {"80c": 125238, "80d": 16348, "80tta": 4692,
                           "80g_eligible_deduction": 0, "80ccd2": 0},
        }), encoding="utf-8")
        evidence = self.client / "01_source" / "deductions" / "80g"
        self.receipt = evidence / "SYNTHETIC_RECEIPT.pdf"
        self.form10be = evidence / "SYNTHETIC_FORM10BE.pdf"
        self.receipt.write_bytes(b"%PDF-1.4\nSYNTHETIC TEST ONLY\n%%EOF")
        self.form10be.write_bytes(b"%PDF-1.4\nSYNTHETIC TEST ONLY\n%%EOF")

    def tearDown(self):
        self.temp.cleanup()

    def run_agent(self, *args, expected=(0,)):
        result = subprocess.run([sys.executable, str(AGENT), *args], text=True,
                                capture_output=True, check=False)
        self.assertIn(result.returncode, expected, result.stdout + result.stderr)
        return result

    def donation(self, **changes):
        row = {
            "donee_name": "Synthetic Donee", "donee_pan": "ABCDE1234F",
            "donee_address": "Synthetic address", "80g_urn": "SYNTHETIC-URN",
            "category": "50_with_limit", "amount": 230000,
            "payment_date": "2026-03-01", "payment_mode": "bank_transfer",
            "payment_reference": "SYNTHETIC-REF", "receipt_number": "SYN-1",
            "receipt_file": str(self.receipt), "form10be_file": str(self.form10be),
        }
        row.update(changes)
        (self.client / "02_extracted" / "donations_80g.json").write_text(
            json.dumps({"donations": [row]}), encoding="utf-8")

    def validation(self):
        self.run_agent("validate-80g", str(self.client), expected=(0, 4))
        return json.loads((self.client / "03_workpapers" / "80g_validation.json").read_text())

    def test_50_percent_limited_calculation(self):
        self.donation()
        result = self.validation()
        self.assertTrue(result["all_rows_valid"])
        self.assertEqual(result["qualifying_limit"], 216439)
        self.assertEqual(result["total_eligible_80g_deduction"], 108220)

    def test_out_of_year_payment_is_rejected(self):
        self.donation(payment_date="2026-07-01")
        result = self.validation()
        self.assertFalse(result["all_rows_valid"])
        self.assertTrue(any("payment_date" in error for error in result["rows"][0]["errors"]))

    def test_cash_above_2000_is_rejected(self):
        self.donation(payment_mode="cash")
        result = self.validation()
        self.assertFalse(result["all_rows_valid"])
        self.assertTrue(any("cash donation" in error for error in result["rows"][0]["errors"]))

    def test_missing_form10be_is_rejected(self):
        self.donation(form10be_file=None)
        result = self.validation()
        self.assertFalse(result["all_rows_valid"])
        self.assertIn("form10be_file is required", result["rows"][0]["errors"])

    def test_add_80g_arguments_hash_evidence_and_validate(self):
        result = self.run_agent(
            "add-80g", str(self.client),
            "--donee-name", "Synthetic Donee", "--donee-pan", "ABCDE1234F",
            "--donee-address", "Synthetic address", "--urn", "SYNTHETIC-URN",
            "--category", "50_with_limit", "--amount", "230000",
            "--payment-date", "2026-03-01", "--payment-mode", "bank_transfer",
            "--payment-reference", "SYNTHETIC-REF", "--receipt-number", "SYN-1",
            "--receipt-file", str(self.receipt), "--form10be-file", str(self.form10be),
        )
        self.assertIn("Added 80G evidence row", result.stdout)
        payload = json.loads((self.client / "02_extracted" / "donations_80g.json").read_text())
        row = payload["donations"][0]
        self.assertEqual(len(row["receipt_sha256"]), 64)
        self.assertEqual(len(row["form10be_sha256"]), 64)
        self.assertEqual(row["donee_pan"], "ABCDE1234F")


if __name__ == "__main__":
    unittest.main(verbosity=2)
