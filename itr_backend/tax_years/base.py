from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft4Validator

from itr_backend.filing_models import (
    CalculationResult,
    FilingProfile,
    NormalizedReturnData,
    PortalValidationResult,
    TaxYearDescriptor,
    ValidationIssue,
)


class TaxYearPolicy(ABC):
    descriptor: TaxYearDescriptor
    schema_path: Path

    @abstractmethod
    def validate_eligibility(
        self, profile: FilingProfile, data: NormalizedReturnData
    ) -> list[ValidationIssue]:
        raise NotImplementedError

    @abstractmethod
    def calculate(self, data: NormalizedReturnData, regime: str) -> CalculationResult:
        raise NotImplementedError

    def validate_portal_payload(
        self, payload: dict[str, Any]
    ) -> PortalValidationResult:
        schema_bytes = self.schema_path.read_bytes()
        actual_checksum = hashlib.sha256(schema_bytes).hexdigest()
        if actual_checksum != self.descriptor.schema_sha256:
            raise RuntimeError(
                f"schema checksum mismatch for {self.descriptor.assessment_year}"
            )
        schema = json.loads(schema_bytes.decode("utf-8-sig"))
        validator = Draft4Validator(schema)
        errors = sorted(
            validator.iter_errors(payload),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
        serialized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return PortalValidationResult(
            assessment_year=self.descriptor.assessment_year,
            schema_version=self.descriptor.schema_version,
            valid=not errors,
            validated_at=datetime.now(timezone.utc),
            payload_sha256=hashlib.sha256(serialized).hexdigest(),
            errors=[
                ValidationIssue(
                    code="PORTAL_SCHEMA",
                    severity="blocker",
                    path="/" + "/".join(map(str, error.absolute_path)),
                    message=error.message,
                )
                for error in errors[:500]
            ],
        )
