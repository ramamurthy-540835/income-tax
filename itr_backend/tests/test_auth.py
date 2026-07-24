from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from itr_backend.app import create_app
from itr_backend.auth import StaticAuthenticator, UserContext
from itr_backend.service import CustomerService
from itr_backend.tests.test_backend import (
    FakeCustomerRepository,
    FakeWorkspaceRepository,
)


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        service = CustomerService(FakeCustomerRepository(), FakeWorkspaceRepository())
        authenticator = StaticAuthenticator(
            UserContext(
                subject="customer-user",
                email="customer@example.com",
                roles={"customer"},
                customer_ids={"cus_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
            )
        )
        self.client = TestClient(
            create_app(
                customer_service=service,
                authenticator=authenticator,
            )
        )

    def test_customer_cannot_list_all_customers(self):
        response = self.client.get("/api/assessment-years/AY_2026-27/customers")
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_access_another_customer(self):
        response = self.client.get(
            "/api/assessment-years/AY_2026-27/customers/"
            "cus_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_create_customer(self):
        response = self.client.post(
            "/api/assessment-years/AY_2026-27/customers",
            json={"display_name": "Unauthorized"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
