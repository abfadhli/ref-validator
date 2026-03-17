"""Verification result models."""

from enum import Enum

from pydantic import BaseModel, Field


class VerificationLevel(int, Enum):
    EXISTENCE = 1
    METADATA = 2
    CLAIMS = 3


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    PARTIAL = "partial"
    ERROR = "error"


class ExistenceResult(BaseModel):
    """Result of checking whether a reference exists."""

    found: bool = False
    source_api: str = Field(default="", description="Which API found it (crossref, semantic_scholar, openalex)")
    matched_doi: str = Field(default="")
    matched_title: str = Field(default="")
    title_similarity: float = Field(default=0.0, description="Fuzzy match score 0-1")
    issues: list[str] = Field(default_factory=list)


class MetadataResult(BaseModel):
    """Result of comparing metadata fields."""

    title_match: bool = False
    authors_match: bool = False
    year_match: bool = False
    venue_match: bool = False
    matched_fields: dict[str, str] = Field(default_factory=dict, description="API values for compared fields")
    issues: list[str] = Field(default_factory=list)


class ClaimVerificationResult(BaseModel):
    """Result of verifying a single claim against source material."""

    claim: str
    supported: bool | None = Field(default=None, description="True/False/None(inconclusive)")
    confidence: float = Field(default=0.0, description="0-1 confidence in the verdict")
    explanation: str = Field(default="")
    source_type: str = Field(default="", description="abstract or full_text")


class CitationVerification(BaseModel):
    """Complete verification result for one reference."""

    ref_id: str
    reference: "Reference | None" = None
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    level_completed: VerificationLevel = VerificationLevel.EXISTENCE
    existence: ExistenceResult | None = None
    metadata: MetadataResult | None = None
    claim_results: list[ClaimVerificationResult] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


# Avoid circular import at runtime
from ref_validator.models.citation import Reference  # noqa: E402

CitationVerification.model_rebuild()
