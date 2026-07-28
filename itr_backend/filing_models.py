from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Regime = Literal["old", "new"]
WorkspaceStatus = Literal[
    "draft",
    "documents_pending",
    "review_pending",
    "ready_for_portal",
    "filed",
    "verified",
]


class BankAccount(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    account_number_last4: str = Field(pattern=r"^\d{4}$")
    ifsc: str = Field(pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")
    bank_name: str = Field(min_length=1, max_length=120)
    account_type: Literal["savings", "current", "cash_credit", "other"] = "savings"
    nominated_for_refund: bool = False


class TaxpayerProfile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    pan: str | None = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    aadhaar_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    date_of_birth: date | None = None
    first_name: str | None = Field(default=None, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    surname: str | None = Field(default=None, max_length=80)
    father_name: str | None = Field(default=None, max_length=160)
    address: dict[str, str] | None = None
    mobile: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=254)
    verification_place: str | None = Field(default=None, max_length=80)
    bank_accounts: list[BankAccount] = Field(default_factory=list, max_length=20)

    @field_validator("bank_accounts")
    @classmethod
    def require_single_refund_account(
        cls, accounts: list[BankAccount]
    ) -> list[BankAccount]:
        if sum(account.nominated_for_refund for account in accounts) > 1:
            raise ValueError("only one bank account can be nominated for refund")
        return accounts


class EligibilityAnswers(BaseModel):
    resident_and_ordinarily_resident: bool | None = None
    no_business_or_professional_income: bool | None = None
    not_company_director: bool | None = None
    no_unlisted_equity_shares: bool | None = None
    no_foreign_assets_signing_authority_or_income: bool | None = None
    no_tds_under_194n: bool | None = None
    no_deferred_esop_tax: bool | None = None
    no_brought_forward_or_carry_forward_loss: bool | None = None
    no_short_term_capital_gain: bool | None = None
    no_section_5a_apportionment: bool | None = None
    no_excluded_special_rate_other_income: bool | None = None


class FilingProfile(BaseModel):
    taxpayer: TaxpayerProfile = Field(default_factory=TaxpayerProfile)
    eligibility: EligibilityAnswers = Field(default_factory=EligibilityAnswers)


class ClientOnboardingRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    preferred_regime: Literal["old", "new", "compare"] = "compare"
    is_active: bool = True
    profile: FilingProfile


class HousePropertyIncome(BaseModel):
    property_type: Literal["self_occupied", "let_out", "deemed_let_out"]
    net_income_or_loss: Decimal = Decimal("0")
    unrealized_rent: Decimal = Field(default=Decimal("0"), ge=0)


class IncomeDetails(BaseModel):
    gross_salary: Decimal = Field(default=Decimal("0"), ge=0)
    exempt_salary_allowances: Decimal = Field(default=Decimal("0"), ge=0)
    professional_tax: Decimal = Field(default=Decimal("0"), ge=0)
    savings_interest: Decimal = Field(default=Decimal("0"), ge=0)
    deposit_interest: Decimal = Field(default=Decimal("0"), ge=0)
    dividend_income: Decimal = Field(default=Decimal("0"), ge=0)
    family_pension: Decimal = Field(default=Decimal("0"), ge=0)
    other_ordinary_income: Decimal = Field(default=Decimal("0"), ge=0)
    agricultural_income: Decimal = Field(default=Decimal("0"), ge=0)
    long_term_capital_gain_112a: Decimal = Field(default=Decimal("0"), ge=0)
    short_term_capital_gain: Decimal = Field(default=Decimal("0"), ge=0)
    business_or_professional_income: Decimal = Field(default=Decimal("0"), ge=0)
    excluded_special_rate_income: Decimal = Field(default=Decimal("0"), ge=0)
    house_properties: list[HousePropertyIncome] = Field(
        default_factory=list, max_length=2
    )


class DeductionDetails(BaseModel):
    section_80c_80ccc_80ccd1: Decimal = Field(default=Decimal("0"), ge=0)
    section_80ccd1b: Decimal = Field(default=Decimal("0"), ge=0)
    section_80ccd2: Decimal = Field(default=Decimal("0"), ge=0)
    section_80d: Decimal = Field(default=Decimal("0"), ge=0)
    section_80dd: Decimal = Field(default=Decimal("0"), ge=0)
    section_80ddb: Decimal = Field(default=Decimal("0"), ge=0)
    section_80e: Decimal = Field(default=Decimal("0"), ge=0)
    section_80ee: Decimal = Field(default=Decimal("0"), ge=0)
    section_80eea: Decimal = Field(default=Decimal("0"), ge=0)
    section_80eeb: Decimal = Field(default=Decimal("0"), ge=0)
    section_80g: Decimal = Field(default=Decimal("0"), ge=0)
    section_80gga: Decimal = Field(default=Decimal("0"), ge=0)
    section_80ggc: Decimal = Field(default=Decimal("0"), ge=0)
    section_80tta: Decimal = Field(default=Decimal("0"), ge=0)
    section_80ttb: Decimal = Field(default=Decimal("0"), ge=0)
    section_80u: Decimal = Field(default=Decimal("0"), ge=0)
    other_eligible_old_regime: Decimal = Field(default=Decimal("0"), ge=0)


class TaxPaidDetails(BaseModel):
    tds_salary: Decimal = Field(default=Decimal("0"), ge=0)
    tds_other: Decimal = Field(default=Decimal("0"), ge=0)
    tcs: Decimal = Field(default=Decimal("0"), ge=0)
    advance_tax: Decimal = Field(default=Decimal("0"), ge=0)
    self_assessment_tax: Decimal = Field(default=Decimal("0"), ge=0)

    @property
    def total(self) -> Decimal:
        return (
            self.tds_salary
            + self.tds_other
            + self.tcs
            + self.advance_tax
            + self.self_assessment_tax
        )


class FilingDetails(BaseModel):
    return_type: Literal["original", "belated", "revised"] = "original"
    regime: Regime = "new"
    original_acknowledgement_number: str | None = None
    original_filing_date: date | None = None
    due_date: date | None = None
    expected_filing_date: date | None = None

    @field_validator("original_acknowledgement_number")
    @classmethod
    def revised_return_reference_required(cls, value: str | None, info) -> str | None:
        return value


class NormalizedReturnData(BaseModel):
    assessment_year: str
    age_band: Literal["below_60", "senior", "super_senior"]
    filing: FilingDetails = Field(default_factory=FilingDetails)
    income: IncomeDetails = Field(default_factory=IncomeDetails)
    deductions: DeductionDetails = Field(default_factory=DeductionDetails)
    tax_paid: TaxPaidDetails = Field(default_factory=TaxPaidDetails)


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["blocker", "warning"]
    path: str
    message: str


class DonationPlanning(BaseModel):
    regime_eligible: bool
    adjusted_total_income: int
    limited_category_qualifying_ceiling: int
    max_donation_100_percent_limited: int
    max_deduction_100_percent_limited: int
    estimated_tax_saving_100_percent_limited: int
    max_donation_50_percent_limited: int
    max_deduction_50_percent_limited: int
    estimated_tax_saving_50_percent_limited: int
    notes: list[str] = Field(default_factory=list)


class CalculationResult(BaseModel):
    assessment_year: str
    regime: Regime
    gross_total_income: int
    total_deductions: int
    total_income: int
    normal_rate_tax: int
    special_rate_tax: int
    rebate_87a: int
    cess: int
    total_tax: int
    taxes_paid: int
    balance_payable: int
    refund: int
    donation_planning: DonationPlanning | None = None
    advisory_only: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)


class ExtractedTaxFacts(BaseModel):
    document_id: str
    document_type: str
    issuer: str | None = None
    financial_year: str | None = None
    assessment_year: str | None = None
    taxpayer_name: str | None = None
    gross_salary: Decimal = Field(default=Decimal("0"), ge=0)
    exempt_salary_allowances: Decimal = Field(default=Decimal("0"), ge=0)
    professional_tax: Decimal = Field(default=Decimal("0"), ge=0)
    savings_interest: Decimal = Field(default=Decimal("0"), ge=0)
    deposit_interest: Decimal = Field(default=Decimal("0"), ge=0)
    dividend_income: Decimal = Field(default=Decimal("0"), ge=0)
    tds_salary: Decimal = Field(default=Decimal("0"), ge=0)
    tds_other: Decimal = Field(default=Decimal("0"), ge=0)
    section_80c: Decimal = Field(default=Decimal("0"), ge=0)
    section_80d: Decimal = Field(default=Decimal("0"), ge=0)
    section_80tta: Decimal = Field(default=Decimal("0"), ge=0)
    evidence_quality: Literal["high", "medium", "low"] = "low"
    notes: list[str] = Field(default_factory=list)


class ReconciledTaxFacts(BaseModel):
    gross_salary: int
    exempt_salary_allowances: int
    professional_tax: int
    savings_interest: int
    deposit_interest: int
    dividend_income: int
    tds_salary: int
    tds_other: int
    section_80c: int
    section_80d: int
    section_80tta: int
    source_document_ids: list[str]
    warnings: list[str] = Field(default_factory=list)


class AutomatedTaxCalculation(BaseModel):
    reconciled: ReconciledTaxFacts
    old_before_donation: CalculationResult
    maximum_useful_donation_50_percent_limited: int
    eligible_80g_deduction: int
    old_after_donation: CalculationResult
    tax_reduction_from_donation: int
    new_regime: CalculationResult | None = None
    extracted_documents: list[ExtractedTaxFacts]
    review_required: bool = True


class TaxYearDescriptor(BaseModel):
    assessment_year: str
    financial_year: str
    form: Literal["ITR-1"]
    policy_version: str
    schema_version: str
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    enabled: bool
    official_schema_release_date: date
    official_validation_release_date: date


class PortalDraft(BaseModel):
    payload: dict[str, Any]
    source: Literal["portal_prefill", "offline_utility", "manual_import"] = (
        "manual_import"
    )


class PortalValidationResult(BaseModel):
    assessment_year: str
    schema_version: str
    valid: bool
    validated_at: datetime
    payload_sha256: str
    errors: list[ValidationIssue]
    portal_business_validation_required: bool = True


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str = Field(min_length=1, max_length=2000)
    portal_validation_completed: bool = False


class FilingEvidence(BaseModel):
    acknowledgement_number: str = Field(min_length=1, max_length=50)
    filed_at: datetime
    filing_section: str = Field(min_length=1, max_length=30)
    verification_status: Literal[
        "pending", "e_verified", "itr_v_posted", "verified"
    ] = "pending"
    verification_date: datetime | None = None


class WorkspaceSummary(BaseModel):
    customer_id: str
    assessment_year: str
    status: WorkspaceStatus
    profile_complete: bool
    normalized_return_present: bool
    portal_draft_present: bool
    schema_valid: bool
    preparer_approved: bool
    portal_validation_completed: bool
    filing_evidence_present: bool
    blockers: list[ValidationIssue]
