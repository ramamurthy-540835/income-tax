from __future__ import annotations

from itr_backend.models import normalize_assessment_year
from itr_backend.tax_years.base import TaxYearPolicy


class UnsupportedTaxYearError(ValueError):
    pass


def _policies() -> dict[str, TaxYearPolicy]:
    from itr_backend.tax_years.ay_2026_27 import AY202627Policy

    policy = AY202627Policy()
    return {policy.descriptor.assessment_year: policy}


def get_tax_year(assessment_year: str) -> TaxYearPolicy:
    normalized = normalize_assessment_year(assessment_year)
    policy = _policies().get(normalized)
    if policy is None or not policy.descriptor.enabled:
        raise UnsupportedTaxYearError(
            f"{normalized} is not enabled; install and approve its official "
            "ITR-1 policy, schema, and validation release first"
        )
    return policy


def list_tax_years():
    return [policy.descriptor for policy in _policies().values()]
