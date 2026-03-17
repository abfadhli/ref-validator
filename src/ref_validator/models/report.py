"""Validation report model."""

from datetime import datetime

from pydantic import BaseModel, Field

from ref_validator.models.cost import CostSummary
from ref_validator.models.verification import (
    CitationVerification,
    VerificationLevel,
    VerificationStatus,
)


class ValidationReport(BaseModel):
    """Top-level validation report."""

    paper_path: str
    timestamp: datetime = Field(default_factory=datetime.now)
    verification_level: VerificationLevel
    total_references: int = 0
    results: list[CitationVerification] = Field(default_factory=list)
    cost_summary: CostSummary | None = None

    @property
    def verified_count(self) -> int:
        return sum(1 for r in self.results if r.status == VerificationStatus.VERIFIED)

    @property
    def unverified_count(self) -> int:
        return sum(1 for r in self.results if r.status == VerificationStatus.UNVERIFIED)

    @property
    def partial_count(self) -> int:
        return sum(1 for r in self.results if r.status == VerificationStatus.PARTIAL)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == VerificationStatus.ERROR)
