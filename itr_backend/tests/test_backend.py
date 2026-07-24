from __future__ import annotations

import unittest
from collections.abc import Iterator

from fastapi.testclient import TestClient

from itr_backend.app import create_app
from itr_backend.models import CustomerCreate, CustomerRecord
from itr_backend.repositories import CustomerAlreadyExistsError
from itr_backend.service import CustomerProvisioningError, CustomerService


class FakeCustomerRepository:
    def __init__(self):
        self.global_ids: set[str] = set()
        self.records: dict[tuple[str, str], CustomerRecord] = {}

    def reserve(self, customer: CustomerRecord) -> None:
        if customer.customer_id in self.global_ids:
            raise CustomerAlreadyExistsError(customer.customer_id)
        self.global_ids.add(customer.customer_id)
        self.records[(customer.assessment_year, customer.customer_id)] = customer

    def set_status(self, assessment_year: str, customer_id: str, status: str) -> None:
        key = (assessment_year, customer_id)
        self.records[key] = self.records[key].model_copy(update={"status": status})

    def get(self, assessment_year: str, customer_id: str) -> CustomerRecord | None:
        return self.records.get((assessment_year, customer_id))

    def list(self, assessment_year: str) -> list[CustomerRecord]:
        return [
            record for (ay, _), record in self.records.items() if ay == assessment_year
        ]


class FakeWorkspaceRepository:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.initialized: list[CustomerRecord] = []
        self.deleted: list[str] = []

    def initialize(self, customer: CustomerRecord) -> None:
        if self.fail:
            raise RuntimeError("simulated GCS failure")
        self.initialized.append(customer)

    def delete(self, workspace_prefix: str) -> None:
        self.deleted.append(workspace_prefix)


def sequence(values: list[str]) -> Iterator[str]:
    yield from values


class CustomerServiceTests(unittest.TestCase):
    def setUp(self):
        self.customers = FakeCustomerRepository()
        self.workspaces = FakeWorkspaceRepository()
        self.ids = sequence(
            [
                "cus_11111111111111111111111111111111",
                "cus_22222222222222222222222222222222",
            ]
        )
        self.service = CustomerService(
            self.customers,
            self.workspaces,
            id_factory=lambda: next(self.ids),
        )

    def test_customer_ids_are_unique_and_global(self):
        first = self.service.create(
            "2026-27", CustomerCreate(display_name="First Customer")
        )
        second = self.service.create(
            "AY_2026-27", CustomerCreate(display_name="Second Customer")
        )

        self.assertNotEqual(first.customer_id, second.customer_id)
        self.assertEqual(first.status, "active")
        self.assertEqual(
            first.workspace_prefix,
            "assessment-years/AY_2026-27/customers/"
            "cus_11111111111111111111111111111111/",
        )

    def test_collision_is_retried(self):
        self.customers.global_ids.add("cus_collision")
        ids = sequence(["cus_collision", "cus_unique"])
        service = CustomerService(
            self.customers,
            self.workspaces,
            id_factory=lambda: next(ids),
        )

        customer = service.create("2026-27", CustomerCreate(display_name="Customer"))

        self.assertEqual(customer.customer_id, "cus_unique")

    def test_workspace_failure_marks_customer_failed(self):
        ids = sequence(["cus_failed"])
        service = CustomerService(
            self.customers,
            FakeWorkspaceRepository(fail=True),
            id_factory=lambda: next(ids),
        )

        with self.assertRaises(CustomerProvisioningError):
            service.create("2026-27", CustomerCreate(display_name="Customer"))

        record = self.customers.get("AY_2026-27", "cus_failed")
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "provisioning_failed")


class CustomerApiTests(unittest.TestCase):
    def setUp(self):
        ids = sequence(["cus_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"])
        self.service = CustomerService(
            FakeCustomerRepository(),
            FakeWorkspaceRepository(),
            id_factory=lambda: next(ids),
        )
        self.client = TestClient(create_app(self.service))

    def test_create_list_and_get_customer(self):
        created = self.client.post(
            "/api/assessment-years/2026-27/customers",
            json={"display_name": "Example Customer", "preferred_regime": "old"},
        )
        self.assertEqual(created.status_code, 201)
        customer_id = created.json()["customer_id"]

        listed = self.client.get("/api/assessment-years/AY_2026-27/customers")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["customers"]), 1)

        fetched = self.client.get(
            f"/api/assessment-years/AY_2026-27/customers/{customer_id}"
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["display_name"], "Example Customer")

    def test_invalid_assessment_year_is_rejected(self):
        response = self.client.get("/api/assessment-years/AY_2026-29/customers")
        self.assertEqual(response.status_code, 422)

    def test_unknown_customer_returns_404(self):
        response = self.client.get(
            "/api/assessment-years/AY_2026-27/customers/cus_missing"
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
