#!/usr/bin/env python3
"""Evidence-linked, fail-closed Indian ITR preparation CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


RUPEE = Decimal("1")
TEN_RUPEES = Decimal("10")


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def round_rupee(value: Decimal) -> int:
    return int(value.quantize(RUPEE, rounding=ROUND_HALF_UP))


def round_288b(value: Decimal) -> int:
    return int((value / TEN_RUPEES).quantize(RUPEE, rounding=ROUND_HALF_UP) * TEN_RUPEES)


def slab_tax(income: Decimal, slabs: list[tuple[Decimal | None, Decimal]]) -> Decimal:
    tax = Decimal(0)
    lower = Decimal(0)
    for upper, rate in slabs:
        taxable = income - lower if upper is None else min(max(income - lower, 0), upper - lower)
        tax += max(taxable, 0) * rate
        if upper is None or income <= upper:
            break
        lower = upper
    return tax


def new_regime_tax_ay_2026_27(total_income: Decimal) -> Decimal:
    slabs = [
        (money(400000), money(0)), (money(800000), money("0.05")),
        (money(1200000), money("0.10")), (money(1600000), money("0.15")),
        (money(2000000), money("0.20")), (money(2400000), money("0.25")),
        (None, money("0.30")),
    ]
    tax = slab_tax(total_income, slabs)
    if total_income <= money(1200000):
        tax -= min(tax, money(60000))
    elif total_income <= money(1270588):
        # Marginal relief: tax cannot exceed income over ₹12 lakh.
        tax = min(tax, total_income - money(1200000))
    return max(tax, 0)


def old_regime_tax_ay_2026_27(total_income: Decimal, age_band: str) -> Decimal:
    first_limit = {"below_60": 250000, "senior": 300000, "super_senior": 500000}[age_band]
    if age_band == "super_senior":
        slabs = [(money(500000), money(0)), (money(1000000), money("0.20")), (None, money("0.30"))]
    else:
        slabs = [
            (money(first_limit), money(0)), (money(500000), money("0.05")),
            (money(1000000), money("0.20")), (None, money("0.30")),
        ]
    tax = slab_tax(total_income, slabs)
    if total_income <= money(500000):
        tax -= min(tax, money(12500))
    return max(tax, 0)


@dataclass
class RegimeResult:
    regime: str
    gross_total_income: int
    deductions: dict[str, int]
    total_deductions: int
    total_income: int
    income_tax_before_cess: int
    cess: int
    total_tax_rounded_288b: int
    tds: int
    balance_payable: int
    refund: int


def calculate_regime(data: dict[str, Any], regime: str) -> RegimeResult:
    salary = money(data["income"]["gross_salary"])
    interest = money(data["income"].get("savings_interest"))
    other = money(data["income"].get("other_ordinary_income"))
    tds = money(data["tax_paid"].get("tds"))
    age_band = data["taxpayer"].get("age_band")
    if age_band not in {"below_60", "senior", "super_senior"}:
        raise ValueError("taxpayer.age_band must be below_60, senior, or super_senior")

    standard_deduction = money(75000 if regime == "new" else 50000)
    salary_income = max(salary - standard_deduction, 0)
    gti = salary_income + interest + other
    deductions: dict[str, Decimal]
    if regime == "new":
        deductions = {"standard_deduction_16ia": standard_deduction}
        total_chapter_via = money(data["deductions"].get("80ccd2", 0))
        if total_chapter_via:
            deductions["80CCD2"] = total_chapter_via
    else:
        d80c = min(money(data["deductions"].get("80c", 0)), money(150000))
        d80d = money(data["deductions"].get("80d", 0))
        d80tta = min(money(data["deductions"].get("80tta", 0)), interest, money(10000))
        d80g = money(data["deductions"].get("80g_eligible_deduction", 0))
        deductions = {
            "standard_deduction_16ia": standard_deduction,
            "80C": d80c, "80D": d80d, "80TTA": d80tta, "80G": d80g,
        }
        total_chapter_via = d80c + d80d + d80tta + d80g

    total_income = max(gti - total_chapter_via, 0)
    tax = new_regime_tax_ay_2026_27(total_income) if regime == "new" else old_regime_tax_ay_2026_27(total_income, age_band)
    cess = tax * money("0.04")
    final_tax = money(round_288b(tax + cess))
    return RegimeResult(
        regime=regime,
        gross_total_income=round_rupee(gti),
        deductions={k: round_rupee(v) for k, v in deductions.items()},
        total_deductions=round_rupee(total_chapter_via),
        total_income=round_288b(total_income),
        income_tax_before_cess=round_rupee(tax),
        cess=round_rupee(cess),
        total_tax_rounded_288b=int(final_tax),
        tds=round_rupee(tds),
        balance_payable=max(int(final_tax - tds), 0),
        refund=max(int(tds - final_tax), 0),
    )


def donation_analysis(data: dict[str, Any]) -> dict[str, int | str]:
    salary = money(data["income"]["gross_salary"])
    interest = money(data["income"].get("savings_interest"))
    other = money(data["income"].get("other_ordinary_income"))
    gti_old = max(salary - money(50000), 0) + interest + other
    non_80g = (
        min(money(data["deductions"].get("80c", 0)), money(150000))
        + money(data["deductions"].get("80d", 0))
        + min(money(data["deductions"].get("80tta", 0)), interest, money(10000))
    )
    adjusted_gti = max(gti_old - non_80g, 0)
    limit = adjusted_gti * money("0.10")
    return {
        "adjusted_gti": round_rupee(adjusted_gti),
        "qualifying_limit_for_limited_80g_donations": round_rupee(limit),
        "max_deduction_if_100_percent_with_limit": round_rupee(limit),
        "max_deduction_if_50_percent_with_limit": round_rupee(money(round_rupee(limit)) * money("0.50")),
        "cash_warning": "Cash donation above Rs 2,000 is not deductible.",
        "timing_warning": "Only donations made during FY 2025-26 can be claimed in AY 2026-27.",
    }


BLOCKING_ELIGIBILITY = [
    "resident_and_ordinarily_resident", "total_income_not_over_50_lakh",
    "no_business_or_professional_income", "not_company_director",
    "no_unlisted_equity_shares", "no_foreign_assets_or_foreign_income",
    "not_subject_to_etr_proviso", "not_nri_or_rnor", "no_brought_forward_loss",
    "not_more_than_one_house_property", "no_special_rate_income_except_permitted_112a",
]

SOURCE_FOLDERS = [
    "01_source/ais", "01_source/form16", "01_source/26as", "01_source/tis",
    "01_source/bank", "01_source/deductions/80c", "01_source/deductions/80d",
    "01_source/deductions/80g", "01_source/house_property",
    "01_source/capital_gains", "01_source/other", "02_extracted",
    "03_workpapers", "04_portal_export", "05_filing_evidence",
    "06_correspondence", "99_excluded_or_future_year",
]

DONATION_CATEGORIES = {
    "100_without_limit": (money("1.00"), False),
    "50_without_limit": (money("0.50"), False),
    "100_with_limit": (money("1.00"), True),
    "50_with_limit": (money("0.50"), True),
}


def readiness(profile: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key in BLOCKING_ELIGIBILITY:
        if profile.get("eligibility", {}).get(key) is not True:
            blockers.append(f"eligibility.{key} must be confirmed true")
    for key in ["pan", "dob", "first_name", "surname", "father_name", "address", "mobile", "email", "bank_accounts", "verification_place"]:
        if not profile.get("taxpayer", {}).get(key):
            blockers.append(f"taxpayer.{key} is required")
    return blockers


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command_init(client: Path, client_id: str, ay: str, regime: str) -> int:
    client.mkdir(parents=True, exist_ok=True)
    for relative in SOURCE_FOLDERS:
        (client / relative).mkdir(parents=True, exist_ok=True)
    config_path = client / "client_config.json"
    if not config_path.exists():
        write_json(config_path, {
            "client_id": client_id, "assessment_year": ay,
            "preferred_regime": regime, "password_env_vars": [],
            "preparer_review_required": True,
            "portal_submission_mode": "manual_after_validation",
        })
    profile_path = client / "02_extracted" / "client_profile.json"
    if not profile_path.exists():
        write_json(profile_path, {
            "taxpayer": {
                "pan": None, "dob": None, "first_name": None, "middle_name": None,
                "surname": None, "father_name": None, "address": None,
                "mobile": None, "email": None, "bank_accounts": None,
                "verification_place": None,
            },
            "eligibility": {key: None for key in BLOCKING_ELIGIBILITY},
        })
    donations_path = client / "02_extracted" / "donations_80g.json"
    if not donations_path.exists():
        write_json(donations_path, {"donations": []})
    print(f"Initialized client workspace: {client}")
    return 0


def command_index(client: Path) -> int:
    rows = []
    for path in sorted((client / "01_source").rglob("*.pdf")):
        rows.append({
            "relative_path": path.relative_to(client).as_posix(),
            "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
        })
    output = {"client_folder": client.name, "document_count": len(rows), "documents": rows}
    write_json(client / "02_extracted" / "evidence_manifest.json", output)
    print(json.dumps(output, indent=2))
    return 0


def validate_pan(pan: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan.upper()))


def donation_fy_bounds(assessment_year: str) -> tuple[str, str]:
    start_year = int(assessment_year.split("-")[0]) - 1
    return f"{start_year}-04-01", f"{start_year + 1}-03-31"


def command_validate_80g(client: Path) -> int:
    data = load_json(client / "02_extracted" / "return_data.json")
    payload = load_json(client / "02_extracted" / "donations_80g.json")
    ay = data.get("assessment_year", "2026-27")
    fy_start, fy_end = donation_fy_bounds(ay)
    analysis = donation_analysis(data)
    remaining_limit = money(analysis["qualifying_limit_for_limited_80g_donations"])
    total_deduction = money(0)
    results = []
    for row_number, donation in enumerate(payload.get("donations", []), 1):
        errors: list[str] = []
        pan = str(donation.get("donee_pan", "")).upper()
        category = donation.get("category")
        amount = money(donation.get("amount"))
        date = str(donation.get("payment_date") or "")
        mode = str(donation.get("payment_mode") or "").lower()
        if not validate_pan(pan): errors.append("donee_pan is invalid")
        if category not in DONATION_CATEGORIES: errors.append("category is invalid or unverified")
        if not (fy_start <= date <= fy_end): errors.append(f"payment_date must be within {fy_start} to {fy_end}")
        if amount <= 0: errors.append("amount must be positive")
        if mode == "cash" and amount > 2000: errors.append("cash donation above Rs 2,000 is not deductible")
        for field in ("donee_name", "donee_address", "80g_urn", "receipt_number", "receipt_file", "form10be_file", "payment_reference"):
            if not donation.get(field): errors.append(f"{field} is required")
        deduction = money(0)
        if not errors:
            rate, limited = DONATION_CATEGORIES[category]
            qualifying_amount = min(amount, remaining_limit) if limited else amount
            deduction = qualifying_amount * rate
            if limited: remaining_limit = max(remaining_limit - qualifying_amount, 0)
            total_deduction += deduction
        results.append({"row": row_number, "donee_pan": pan, "amount": round_rupee(amount), "category": category, "eligible_deduction": round_rupee(deduction), "valid": not errors, "errors": errors})
    output = {
        "assessment_year": ay, "financial_year_window": [fy_start, fy_end],
        "qualifying_limit": analysis["qualifying_limit_for_limited_80g_donations"],
        "total_eligible_80g_deduction": round_rupee(total_deduction),
        "all_rows_valid": all(row["valid"] for row in results) and bool(results),
        "rows": results,
        "control": "Receipt and Form 10BE must be issued by the donee; this agent does not create them.",
    }
    write_json(client / "03_workpapers" / "80g_validation.json", output)
    print(json.dumps(output, indent=2))
    return 0 if output["all_rows_valid"] else 4


def command_add_80g(client: Path, args: argparse.Namespace) -> int:
    receipt = Path(args.receipt_file).expanduser().resolve()
    form10be = Path(args.form10be_file).expanduser().resolve()
    if not receipt.is_file():
        raise ValueError(f"Receipt file not found: {receipt}")
    if not form10be.is_file():
        raise ValueError(f"Form 10BE file not found: {form10be}")
    if not validate_pan(args.donee_pan):
        raise ValueError("Invalid donee PAN format")
    if args.payment_mode.lower() == "cash" and money(args.amount) > 2000:
        raise ValueError("Cash donation above Rs 2,000 is not deductible")
    donation_path = client / "02_extracted" / "donations_80g.json"
    payload = load_json(donation_path) if donation_path.exists() else {"donations": []}
    row = {
        "donee_name": args.donee_name,
        "donee_pan": args.donee_pan.upper(),
        "donee_address": args.donee_address,
        "80g_urn": args.urn,
        "category": args.category,
        "amount": round_rupee(money(args.amount)),
        "payment_date": args.payment_date,
        "payment_mode": args.payment_mode.lower(),
        "payment_reference": args.payment_reference,
        "receipt_number": args.receipt_number,
        "receipt_file": receipt.relative_to(client).as_posix() if receipt.is_relative_to(client) else str(receipt),
        "receipt_sha256": sha256_file(receipt),
        "form10be_file": form10be.relative_to(client).as_posix() if form10be.is_relative_to(client) else str(form10be),
        "form10be_sha256": sha256_file(form10be),
    }
    rows = payload.setdefault("donations", [])
    replaced = False
    for index, existing in enumerate(rows):
        if str(existing.get("donee_pan", "")).upper() == row["donee_pan"] and int(existing.get("amount", 0) or 0) == row["amount"]:
            rows[index] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)
    write_json(donation_path, payload)
    print(f"{'Updated' if replaced else 'Added'} 80G evidence row for {row['donee_name']}.")
    return command_validate_80g(client)


def command_validate_portal_json(client: Path, schema_path: Path, json_path: Path) -> int:
    from jsonschema import Draft4Validator
    errors = sorted(Draft4Validator(load_json(schema_path)).iter_errors(load_json(json_path)), key=lambda e: list(e.path))
    report = {
        "schema": str(schema_path), "portal_json": str(json_path), "schema_valid": not errors,
        "errors": [{"path": "/".join(map(str, e.path)), "message": e.message} for e in errors[:200]],
        "warning": "Schema validity does not replace portal business-rule validation or preparer review.",
    }
    write_json(client / "03_workpapers" / "portal_schema_validation.json", report)
    print(json.dumps(report, indent=2))
    return 0 if not errors else 5


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def command_calculate(client: Path) -> int:
    data = load_json(client / "02_extracted" / "return_data.json")
    validation_path = client / "03_workpapers" / "80g_validation.json"
    if validation_path.exists():
        validation = load_json(validation_path)
        if validation.get("all_rows_valid"):
            data.setdefault("deductions", {})["80g_eligible_deduction"] = validation.get("total_eligible_80g_deduction", 0)
    if money(data["income"].get("special_rate_income")) or money(data["income"].get("business_income")):
        raise ValueError("Special-rate or business income requires a broader return engine")
    if money(data["income"]["gross_salary"]) + money(data["income"].get("savings_interest")) >= money(5000000):
        raise ValueError("Income at or above Rs 50 lakh is outside this ITR-1 calculator")
    old = calculate_regime(data, "old")
    new = calculate_regime(data, "new")
    result = {
        "assessment_year": "2026-27",
        "old_regime": asdict(old), "new_regime": asdict(new),
        "recommended_regime_on_verified_numbers": "old" if old.total_tax_rounded_288b < new.total_tax_rounded_288b else "new",
        "tax_difference": abs(old.total_tax_rounded_288b - new.total_tax_rounded_288b),
        "80g_analysis": donation_analysis(data),
        "warnings": data.get("warnings", []),
    }
    output = client / "03_workpapers" / "tax_comparison.json"
    write_json(output, result)
    print(json.dumps(result, indent=2))
    print(f"\nSaved: {output}")
    return 0


def command_readiness(client: Path) -> int:
    profile = load_json(client / "02_extracted" / "client_profile.json")
    blockers = readiness(profile)
    output = {"upload_ready": not blockers, "blockers": blockers}
    write_json(client / "03_workpapers" / "filing_readiness.json", output)
    print(json.dumps(output, indent=2))
    return 0 if not blockers else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("init", "index", "add-80g", "calculate", "readiness", "validate-80g", "validate-portal-json"))
    parser.add_argument("client_folder")
    parser.add_argument("--client-id", default="")
    parser.add_argument("--assessment-year", default="2026-27")
    parser.add_argument("--regime", choices=("old", "new", "compare"), default="old")
    parser.add_argument("--schema")
    parser.add_argument("--portal-json")
    parser.add_argument("--donee-name")
    parser.add_argument("--donee-pan")
    parser.add_argument("--donee-address")
    parser.add_argument("--urn")
    parser.add_argument("--category", choices=tuple(DONATION_CATEGORIES))
    parser.add_argument("--amount", type=Decimal)
    parser.add_argument("--payment-date")
    parser.add_argument("--payment-mode", choices=("upi", "bank_transfer", "cheque", "card", "cash", "other"))
    parser.add_argument("--payment-reference")
    parser.add_argument("--receipt-number")
    parser.add_argument("--receipt-file")
    parser.add_argument("--form10be-file")
    args = parser.parse_args()
    client = Path(args.client_folder).resolve()
    if args.command == "init":
        return command_init(client, args.client_id or client.name, args.assessment_year, args.regime)
    if not client.is_dir():
        print(f"Client folder not found: {client}", file=sys.stderr)
        return 2
    if args.command == "index": return command_index(client)
    if args.command == "add-80g":
        required = ("donee_name", "donee_pan", "donee_address", "urn", "category", "amount", "payment_date", "payment_mode", "payment_reference", "receipt_number", "receipt_file", "form10be_file")
        missing = [name.replace("_", "-") for name in required if getattr(args, name) in (None, "")]
        if missing:
            raise ValueError("Missing add-80g arguments: --" + ", --".join(missing))
        return command_add_80g(client, args)
    if args.command == "calculate": return command_calculate(client)
    if args.command == "readiness": return command_readiness(client)
    if args.command == "validate-80g": return command_validate_80g(client)
    if not args.schema or not args.portal_json:
        raise ValueError("--schema and --portal-json are required")
    return command_validate_portal_json(client, Path(args.schema), Path(args.portal_json))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
