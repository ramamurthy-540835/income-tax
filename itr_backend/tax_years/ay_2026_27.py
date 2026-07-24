from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from itr_backend.filing_models import (
    CalculationResult,
    FilingProfile,
    NormalizedReturnData,
    TaxYearDescriptor,
    ValidationIssue,
)
from itr_backend.tax_years.base import TaxYearPolicy

RUPEE = Decimal("1")
TEN_RUPEES = Decimal("10")


def _money(value) -> Decimal:
    return Decimal(str(value or 0))


def _round_rupee(value: Decimal) -> int:
    return int(value.quantize(RUPEE, rounding=ROUND_HALF_UP))


def _round_288b(value: Decimal) -> int:
    return int(
        (value / TEN_RUPEES).quantize(RUPEE, rounding=ROUND_HALF_UP) * TEN_RUPEES
    )


def _slab_tax(income: Decimal, slabs: list[tuple[Decimal | None, Decimal]]) -> Decimal:
    tax = Decimal("0")
    lower = Decimal("0")
    for upper, rate in slabs:
        taxable = (
            income - lower
            if upper is None
            else min(max(income - lower, 0), upper - lower)
        )
        tax += max(taxable, 0) * rate
        if upper is None or income <= upper:
            break
        lower = upper
    return tax


def _issue(
    code: str, path: str, message: str, severity: str = "blocker"
) -> ValidationIssue:
    return ValidationIssue(code=code, severity=severity, path=path, message=message)


class AY202627Policy(TaxYearPolicy):
    descriptor = TaxYearDescriptor(
        assessment_year="AY_2026-27",
        financial_year="FY_2025-26",
        form="ITR-1",
        policy_version="1.0.0",
        schema_version="1.1",
        schema_sha256="d229b3b814b9d495397bbcb9d7268981834dcdf580ef39cda02f7fbc1b3da3ab",
        enabled=True,
        official_schema_release_date=date(2026, 6, 30),
        official_validation_release_date=date(2026, 5, 15),
    )
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "itr_agent"
        / "schemas"
        / "AY_2026-27"
        / "ITR-1_2026_Main_V1.1.json"
    )

    def validate_portal_payload(self, payload: dict[str, Any]):
        result = super().validate_portal_payload(payload)
        itr = payload.get("ITR")
        if not isinstance(itr, dict) or not isinstance(itr.get("ITR1"), dict):
            result.valid = False
            result.errors.insert(
                0,
                _issue(
                    "PORTAL_ROOT_REQUIRED",
                    "/ITR/ITR1",
                    "official ITR-1 payload must contain the ITR.ITR1 root",
                ),
            )
        return result

    def validate_eligibility(
        self, profile: FilingProfile, data: NormalizedReturnData
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        answers = profile.eligibility.model_dump()
        for field, answer in answers.items():
            if answer is not True:
                issues.append(
                    _issue(
                        "ELIGIBILITY_UNCONFIRMED",
                        f"/profile/eligibility/{field}",
                        f"{field} must be confirmed true for ITR-1",
                    )
                )

        income = data.income
        if len(income.house_properties) > 2:
            issues.append(
                _issue(
                    "HOUSE_PROPERTY_LIMIT",
                    "/income/house_properties",
                    "ITR-1 permits income from at most two house properties",
                )
            )
        if income.long_term_capital_gain_112a > _money(125000):
            issues.append(
                _issue(
                    "LTCG_112A_LIMIT",
                    "/income/long_term_capital_gain_112a",
                    "ITR-1 permits section 112A LTCG only up to Rs 1,25,000",
                )
            )
        if income.agricultural_income > _money(5000):
            issues.append(
                _issue(
                    "AGRICULTURAL_INCOME_LIMIT",
                    "/income/agricultural_income",
                    "ITR-1 permits agricultural income only up to Rs 5,000",
                )
            )
        prohibited = {
            "short_term_capital_gain": income.short_term_capital_gain,
            "business_or_professional_income": (income.business_or_professional_income),
            "excluded_special_rate_income": income.excluded_special_rate_income,
        }
        for field, value in prohibited.items():
            if value:
                issues.append(
                    _issue(
                        "INCOME_NOT_SUPPORTED_BY_ITR1",
                        f"/income/{field}",
                        f"{field} is not permitted in ITR-1",
                    )
                )

        normal_income = (
            income.gross_salary
            + income.savings_interest
            + income.deposit_interest
            + income.dividend_income
            + income.family_pension
            + income.other_ordinary_income
            + sum(
                property_income.net_income_or_loss
                for property_income in income.house_properties
            )
        )
        if normal_income > _money(5000000):
            issues.append(
                _issue(
                    "TOTAL_INCOME_LIMIT",
                    "/income",
                    "ITR-1 is unavailable when total income exceeds Rs 50 lakh",
                )
            )

        filing = data.filing
        if filing.return_type == "revised":
            if not filing.original_acknowledgement_number:
                issues.append(
                    _issue(
                        "REVISED_RETURN_REFERENCE",
                        "/filing/original_acknowledgement_number",
                        "revised return requires the original acknowledgement number",
                    )
                )
            if not filing.original_filing_date:
                issues.append(
                    _issue(
                        "REVISED_RETURN_REFERENCE",
                        "/filing/original_filing_date",
                        "revised return requires the original filing date",
                    )
                )
        if (
            filing.regime == "old"
            and filing.due_date
            and filing.expected_filing_date
            and filing.expected_filing_date > filing.due_date
        ):
            issues.append(
                _issue(
                    "OLD_REGIME_DUE_DATE",
                    "/filing/regime",
                    "portal validation requires timely filing when opting for "
                    "the old regime",
                )
            )
        return issues

    def calculate(self, data: NormalizedReturnData, regime: str) -> CalculationResult:
        if regime not in {"old", "new"}:
            raise ValueError("regime must be old or new")
        income = data.income
        deductions = data.deductions
        issues: list[ValidationIssue] = []

        standard_deduction = _money(75000 if regime == "new" else 50000)
        salary_income = max(
            income.gross_salary
            - income.exempt_salary_allowances
            - standard_deduction
            - (income.professional_tax if regime == "old" else 0),
            0,
        )

        house_income = sum(row.net_income_or_loss for row in income.house_properties)
        if regime == "old":
            house_income = max(house_income, _money(-200000))
        else:
            house_income = max(house_income, _money(0))

        family_pension_limit = _money(25000 if regime == "new" else 15000)
        family_pension_deduction = min(
            income.family_pension / _money(3), family_pension_limit
        )
        other_income = (
            income.savings_interest
            + income.deposit_interest
            + income.dividend_income
            + max(income.family_pension - family_pension_deduction, 0)
            + income.other_ordinary_income
        )
        normal_gti = max(salary_income + house_income + other_income, 0)

        if regime == "new":
            total_deductions = deductions.section_80ccd2
            disallowed = sum(
                value
                for field, value in deductions.model_dump().items()
                if field != "section_80ccd2"
            )
            if disallowed:
                issues.append(
                    _issue(
                        "NEW_REGIME_DEDUCTION",
                        "/deductions",
                        "only supported new-regime deductions may be claimed",
                    )
                )
        else:
            combined_80c = min(deductions.section_80c_80ccc_80ccd1, _money(150000))
            additional_nps = min(deductions.section_80ccd1b, _money(50000))
            interest_deduction = (
                min(deductions.section_80ttb, _money(50000))
                if data.age_band in {"senior", "super_senior"}
                else min(
                    deductions.section_80tta,
                    income.savings_interest,
                    _money(10000),
                )
            )
            total_deductions = (
                combined_80c
                + additional_nps
                + deductions.section_80ccd2
                + deductions.section_80d
                + deductions.section_80dd
                + deductions.section_80ddb
                + deductions.section_80e
                + deductions.section_80ee
                + deductions.section_80eea
                + deductions.section_80eeb
                + deductions.section_80g
                + deductions.section_80gga
                + deductions.section_80ggc
                + interest_deduction
                + deductions.section_80u
                + deductions.other_eligible_old_regime
            )

        total_deductions = min(total_deductions, normal_gti)
        normal_total_income = max(normal_gti - total_deductions, 0)
        ltcg_112a = income.long_term_capital_gain_112a
        total_income = normal_total_income + ltcg_112a

        if regime == "new":
            normal_tax = _slab_tax(
                normal_total_income,
                [
                    (_money(400000), _money(0)),
                    (_money(800000), _money("0.05")),
                    (_money(1200000), _money("0.10")),
                    (_money(1600000), _money("0.15")),
                    (_money(2000000), _money("0.20")),
                    (_money(2400000), _money("0.25")),
                    (None, _money("0.30")),
                ],
            )
            rebate = (
                min(normal_tax, _money(60000))
                if total_income <= _money(1200000)
                else _money(0)
            )
            if _money(1200000) < total_income <= _money(1270588):
                normal_tax = min(normal_tax, total_income - _money(1200000))
        else:
            first_limit = {
                "below_60": 250000,
                "senior": 300000,
                "super_senior": 500000,
            }[data.age_band]
            if data.age_band == "super_senior":
                slabs = [
                    (_money(500000), _money(0)),
                    (_money(1000000), _money("0.20")),
                    (None, _money("0.30")),
                ]
            else:
                slabs = [
                    (_money(first_limit), _money(0)),
                    (_money(500000), _money("0.05")),
                    (_money(1000000), _money("0.20")),
                    (None, _money("0.30")),
                ]
            normal_tax = _slab_tax(normal_total_income, slabs)
            rebate = (
                min(normal_tax, _money(12500))
                if total_income <= _money(500000)
                else _money(0)
            )

        special_taxable = max(ltcg_112a - _money(125000), 0)
        special_tax = special_taxable * _money("0.125")
        tax_after_rebate = max(normal_tax - rebate, 0) + special_tax
        cess = tax_after_rebate * _money("0.04")
        total_tax = _round_288b(tax_after_rebate + cess)
        taxes_paid = _round_rupee(data.tax_paid.total)

        issues.extend(self.validate_eligibility(FilingProfile(), data))
        issues = [issue for issue in issues if issue.code != "ELIGIBILITY_UNCONFIRMED"]
        issues.append(
            _issue(
                "PORTAL_RECOMPUTATION_REQUIRED",
                "/calculation",
                "interest, filing fees, relief, and portal business rules must "
                "be recomputed in the current official utility",
                severity="warning",
            )
        )
        return CalculationResult(
            assessment_year=self.descriptor.assessment_year,
            regime=regime,
            gross_total_income=_round_rupee(normal_gti + ltcg_112a),
            total_deductions=_round_rupee(total_deductions),
            total_income=_round_288b(total_income),
            normal_rate_tax=_round_rupee(normal_tax),
            special_rate_tax=_round_rupee(special_tax),
            rebate_87a=_round_rupee(rebate),
            cess=_round_rupee(cess),
            total_tax=total_tax,
            taxes_paid=taxes_paid,
            balance_payable=max(total_tax - taxes_paid, 0),
            refund=max(taxes_paid - total_tax, 0),
            issues=issues,
        )
