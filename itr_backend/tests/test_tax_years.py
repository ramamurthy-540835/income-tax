from __future__ import annotations

import unittest
from decimal import Decimal

from itr_backend.filing_models import (
    EligibilityAnswers,
    FilingProfile,
    IncomeDetails,
    NormalizedReturnData,
)
from itr_backend.tax_years import get_tax_year
from itr_backend.tax_years.registry import UnsupportedTaxYearError


class TaxYearPolicyTests(unittest.TestCase):
    def test_future_year_is_fail_closed(self):
        with self.assertRaises(UnsupportedTaxYearError):
            get_tax_year("AY_2027-28")

    def test_ay_2026_27_allows_two_house_properties(self):
        policy = get_tax_year("2026-27")
        profile = FilingProfile(
            eligibility=EligibilityAnswers(
                **{field: True for field in EligibilityAnswers.model_fields}
            )
        )
        data = NormalizedReturnData(
            assessment_year="AY_2026-27",
            age_band="below_60",
            income=IncomeDetails(
                gross_salary=Decimal("1000000"),
                house_properties=[
                    {
                        "property_type": "self_occupied",
                        "net_income_or_loss": 0,
                    },
                    {
                        "property_type": "let_out",
                        "net_income_or_loss": 100000,
                        "unrealized_rent": 10000,
                    },
                ],
            ),
        )

        issues = policy.validate_eligibility(profile, data)

        self.assertFalse(any(issue.code == "HOUSE_PROPERTY_LIMIT" for issue in issues))

    def test_exactly_fifty_lakh_is_not_rejected(self):
        policy = get_tax_year("2026-27")
        profile = FilingProfile(
            eligibility=EligibilityAnswers(
                **{field: True for field in EligibilityAnswers.model_fields}
            )
        )
        data = NormalizedReturnData(
            assessment_year="AY_2026-27",
            age_band="below_60",
            income=IncomeDetails(gross_salary=Decimal("5000000")),
        )

        issues = policy.validate_eligibility(profile, data)

        self.assertFalse(any(issue.code == "TOTAL_INCOME_LIMIT" for issue in issues))

    def test_new_regime_computation_and_rebate(self):
        policy = get_tax_year("2026-27")
        data = NormalizedReturnData(
            assessment_year="AY_2026-27",
            age_band="below_60",
            income=IncomeDetails(gross_salary=Decimal("1275000")),
        )

        result = policy.calculate(data, "new")

        self.assertEqual(result.total_income, 1200000)
        self.assertEqual(result.rebate_87a, 60000)
        self.assertEqual(result.total_tax, 0)


if __name__ == "__main__":
    unittest.main()
