from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ASSESSMENT_YEAR_PATTERN = re.compile(r"^(?:AY_)?(\d{4})-(\d{2})$")


def normalize_assessment_year(value: str) -> str:
    match = ASSESSMENT_YEAR_PATTERN.fullmatch(value.strip().upper())
    if not match:
        raise ValueError("assessment year must look like AY_2026-27 or 2026-27")
    start_year = int(match.group(1))
    end_year = int(match.group(2))
    if end_year != (start_year + 1) % 100:
        raise ValueError("assessment year must contain consecutive years")
    return f"AY_{start_year:04d}-{end_year:02d}"


class CustomerCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=160)
    preferred_regime: Literal["old", "new", "compare"] = "compare"

    @field_validator("display_name")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("display_name cannot contain control characters")
        return value


class CustomerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    assessment_year: str
    display_name: str
    preferred_regime: Literal["old", "new", "compare"]
    status: Literal["provisioning", "active", "provisioning_failed"]
    workspace_prefix: str
    created_at: datetime
    updated_at: datetime


class CustomerList(BaseModel):
    assessment_year: str
    customers: list[CustomerRecord]


class HealthResponse(BaseModel):
    status: Literal["ok"]
