from __future__ import annotations

import unittest
from decimal import Decimal

from itr_backend.filing_models import (
    DeductionDetails,
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

    def test_new_regime_slab_boundary_above_rebate_range(self):
        policy = get_tax_year("2026-27")
        data = NormalizedReturnData(
            assessment_year="AY_2026-27",
            age_band="below_60",
            # Rs 16 lakh total income after the Rs 75,000 standard deduction.
            income=IncomeDetails(gross_salary=Decimal("1675000")),
        )

        result = policy.calculate(data, "new")

        self.assertEqual(result.total_income, 1600000)
        self.assertEqual(result.normal_rate_tax, 120000)
        self.assertEqual(result.rebate_87a, 0)
        self.assertEqual(result.cess, 4800)
        self.assertEqual(result.total_tax, 124800)

    def test_old_regime_deductions_and_rebate_boundary(self):
        policy = get_tax_year("2026-27")
        data = NormalizedReturnData(
            assessment_year="AY_2026-27",
            age_band="below_60",
            income=IncomeDetails(gross_salary=Decimal("700000")),
            deductions=DeductionDetails(
                section_80c_80ccc_80ccd1=Decimal("150000")
            ),
        )

        result = policy.calculate(data, "old")

        self.assertEqual(result.total_income, 500000)
        self.assertEqual(result.normal_rate_tax, 12500)
        self.assertEqual(result.rebate_87a, 12500)
        self.assertEqual(result.total_tax, 0)

    def test_80g_is_disallowed_in_new_regime(self):
        policy = get_tax_year("2026-27")
        data = NormalizedReturnData(
            assessment_year="AY_2026-27",
            age_band="below_60",
            income=IncomeDetails(gross_salary=Decimal("1500000")),
            deductions=DeductionDetails(section_80g=Decimal("100000")),
        )

        result = policy.calculate(data, "new")

        self.assertEqual(result.total_deductions, 0)
        self.assertTrue(
            any(issue.code == "NEW_REGIME_DEDUCTION" for issue in result.issues)
        )
        self.assertIsNone(result.donation_planning)

    def test_old_regime_returns_80g_donation_planning_scenarios(self):
        policy = get_tax_year("2026-27")
        data = NormalizedReturnData(
            assessment_year="AY_2026-27",
            age_band="below_60",
            income=IncomeDetails(
                gross_salary=Decimal("1000000"),
                savings_interest=Decimal("10000"),
            ),
            deductions=DeductionDetails(
                section_80c_80ccc_80ccd1=Decimal("150000"),
                section_80d=Decimal("25000"),
                section_80tta=Decimal("10000"),
            ),
        )

        result = policy.calculate(data, "old")
        plan = result.donation_planning

        self.assertIsNotNone(plan)
        self.assertTrue(plan.regime_eligible)
        self.assertEqual(plan.adjusted_total_income, 775000)
        self.assertEqual(plan.limited_category_qualifying_ceiling, 77500)
        self.assertEqual(plan.max_donation_100_percent_limited, 77500)
        self.assertEqual(plan.max_deduction_100_percent_limited, 77500)
        self.assertEqual(plan.estimated_tax_saving_100_percent_limited, 16120)
        self.assertEqual(plan.max_donation_50_percent_limited, 77500)
        self.assertEqual(plan.max_deduction_50_percent_limited, 38750)
        self.assertEqual(plan.estimated_tax_saving_50_percent_limited, 8060)


if __name__ == "__main__":
    unittest.main()
