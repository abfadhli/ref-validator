"""Level 3: Verify that claims are supported by source material."""

import logging

import httpx

from ref_validator.apis.semantic_scholar import SemanticScholarAPI
from ref_validator.apis.unpaywall import UnpaywallAPI
from ref_validator.errors import APIError
from ref_validator.llm.client import LLMClient
from ref_validator.llm.prompts import (
    CLAIM_VERIFICATION_SYSTEM,
    CLAIM_VERIFICATION_TOOL_SCHEMA,
)
from ref_validator.models.citation import InTextCitation
from ref_validator.models.verification import ClaimVerificationResult, ExistenceResult

logger = logging.getLogger(__name__)


async def _get_source_content(
    existence: ExistenceResult,
    *,
    semantic_scholar: SemanticScholarAPI,
    unpaywall: UnpaywallAPI | None,
) -> tuple[str, str]:
    """Get source content for verification. Returns (content, source_type)."""
    # Try abstract first via Semantic Scholar
    if existence.matched_doi:
        try:
            data = await semantic_scholar.get_by_doi(existence.matched_doi)
            abstract = data.get("abstract", "")
            if abstract:
                return abstract, "abstract"
        except APIError:
            pass

    # Try full text via Unpaywall
    if unpaywall and existence.matched_doi:
        pdf_url = await unpaywall.get_oa_pdf_url(existence.matched_doi)
        if pdf_url:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(pdf_url)
                    if resp.status_code == 200 and "pdf" not in resp.headers.get("content-type", ""):
                        # It's likely HTML full text
                        text = resp.text[:50_000]
                        if len(text) > 500:
                            return text, "full_text"
            except Exception:
                logger.warning("Failed to fetch full text from %s", pdf_url)

    return "", ""


async def verify_claim(
    citation: InTextCitation,
    existence: ExistenceResult,
    *,
    llm: LLMClient,
    model: str,
    semantic_scholar: SemanticScholarAPI,
    unpaywall: UnpaywallAPI | None,
) -> ClaimVerificationResult:
    """Verify a single claim against source material."""
    if not citation.claim_made:
        return ClaimVerificationResult(
            claim=citation.surrounding_text,
            supported=None,
            confidence=0.0,
            explanation="No specific claim extracted from citation context",
            source_type="",
        )

    source_content, source_type = await _get_source_content(
        existence, semantic_scholar=semantic_scholar, unpaywall=unpaywall
    )

    if not source_content:
        return ClaimVerificationResult(
            claim=citation.claim_made,
            supported=None,
            confidence=0.0,
            explanation="No source content available for verification",
            source_type="",
        )

    user_message = (
        f"## Claim made in the citing paper\n{citation.claim_made}\n\n"
        f"## Citation context\n{citation.surrounding_text}\n\n"
        f"## Source material ({source_type})\n{source_content}"
    )

    result = await llm.extract_structured(
        model=model,
        system=CLAIM_VERIFICATION_SYSTEM,
        user_message=user_message,
        tool_name="verify_claim",
        tool_schema=CLAIM_VERIFICATION_TOOL_SCHEMA,
    )

    confidence = float(result.get("confidence", 0.0))
    # Reduce confidence when only abstract is available
    if source_type == "abstract":
        confidence *= 0.8

    return ClaimVerificationResult(
        claim=citation.claim_made,
        supported=result.get("supported"),
        confidence=confidence,
        explanation=result.get("explanation", ""),
        source_type=source_type,
    )
