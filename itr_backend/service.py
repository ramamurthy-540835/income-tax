from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from itr_backend.models import (
    CustomerCreate,
    CustomerRecord,
    normalize_assessment_year,
)
from itr_backend.repositories import (
    CustomerAlreadyExistsError,
    CustomerRepository,
    WorkspaceRepository,
)


class CustomerNotFoundError(Exception):
    pass


class CustomerProvisioningError(Exception):
    pass


def generate_customer_id() -> str:
    return f"cus_{uuid.uuid4().hex}"


class CustomerService:
    def __init__(
        self,
        customers: CustomerRepository,
        workspaces: WorkspaceRepository,
        id_factory: Callable[[], str] = generate_customer_id,
    ):
        self._customers = customers
        self._workspaces = workspaces
        self._id_factory = id_factory

    def create(self, assessment_year: str, payload: CustomerCreate) -> CustomerRecord:
        ay = normalize_assessment_year(assessment_year)
        now = datetime.now(timezone.utc)
        customer: CustomerRecord | None = None
        for _ in range(5):
            customer_id = self._id_factory()
            customer = CustomerRecord(
                customer_id=customer_id,
                assessment_year=ay,
                display_name=payload.display_name,
                preferred_regime=payload.preferred_regime,
                status="provisioning",
                workspace_prefix=(f"assessment-years/{ay}/customers/{customer_id}/"),
                created_at=now,
                updated_at=now,
            )
            try:
                self._customers.reserve(customer)
                break
            except CustomerAlreadyExistsError:
                customer = None
        if customer is None:
            raise CustomerProvisioningError("Could not allocate a unique customer ID")

        try:
            self._workspaces.initialize(customer)
            self._customers.set_status(ay, customer.customer_id, "active")
        except Exception as exc:
            try:
                self._workspaces.delete(customer.workspace_prefix)
                self._customers.set_status(
                    ay, customer.customer_id, "provisioning_failed"
                )
            except Exception:
                pass
            raise CustomerProvisioningError(
                "Customer workspace provisioning failed"
            ) from exc

        created = self._customers.get(ay, customer.customer_id)
        if created is None:
            raise CustomerProvisioningError(
                "Customer was provisioned but could not be read"
            )
        return created

    def get(self, assessment_year: str, customer_id: str) -> CustomerRecord:
        ay = normalize_assessment_year(assessment_year)
        customer = self._customers.get(ay, customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    def list(self, assessment_year: str) -> list[CustomerRecord]:
        ay = normalize_assessment_year(assessment_year)
        return self._customers.list(ay)
