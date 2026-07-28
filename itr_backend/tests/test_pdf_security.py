from __future__ import annotations

import io
import unittest
from datetime import date

from pypdf import PdfReader, PdfWriter

from itr_backend.pdf_security import PdfPasswordError, ais_password, unlock_ais_pdf


class AisPasswordTests(unittest.TestCase):
    def test_password_is_lowercase_pan_plus_ddmmyyyy_dob(self):
        self.assertEqual(
            ais_password("ABCDE1234F", date(1990, 1, 2)),
            "abcde1234f02011990",
        )

    def test_encrypted_ais_is_unlocked_for_processing(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("abcde1234f02011990")
        encrypted = io.BytesIO()
        writer.write(encrypted)

        unlocked, pages = unlock_ais_pdf(
            encrypted.getvalue(), "ABCDE1234F", date(1990, 1, 2)
        )

        self.assertEqual(pages, 1)
        self.assertFalse(PdfReader(io.BytesIO(unlocked)).is_encrypted)

    def test_incorrect_profile_details_fail_without_password_fallback(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("different")
        encrypted = io.BytesIO()
        writer.write(encrypted)

        with self.assertRaises(PdfPasswordError):
            unlock_ais_pdf(encrypted.getvalue(), "ABCDE1234F", date(1990, 1, 2))
