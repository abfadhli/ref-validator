"""Level 3: Verify that claims are supported by source material."""

import asyncio
import logging
from difflib import SequenceMatcher
from pathlib import Path

import httpx
import pymupdf

from ref_validator.apis.arxiv import ArxivAPI
from ref_validator.apis.doi_resolver import DOIResolver
from ref_validator.apis.google_scholar import GoogleScholarAPI
from ref_validator.apis.semantic_scholar import SemanticScholarAPI
from ref_validator.apis.unpaywall import UnpaywallAPI
from ref_validator.errors import APIError
from ref_validator.llm.client import LLMClient
from ref_validator.llm.prompts import (
    CLAIM_VERIFICATION_SYSTEM,
    CLAIM_VERIFICATION_TOOL_SCHEMA,
)
from ref_validator.models.citation import InTextCitation, Reference
from ref_validator.models.verification import ClaimVerificationResult, ExistenceResult

logger = logging.getLogger(__name__)

# Minimum ratio for arXiv title match (pre-fetch and post-fetch)
_ARXIV_TITLE_THRESHOLD = 0.90


def _validate_content(text: str, reference: Reference, existence: ExistenceResult) -> bool:
    """Verify that fetched content actually belongs to the expected paper.

    Checks whether the text contains the expected title or at least one author
    last name. This catches cases where a source returns the wrong paper,
    a landing page, or a document listing.
    """
    if not text:
        return False

    text_lower = text[:10_000].lower()  # only check the beginning

    # Check for title presence (normalized)
    expected_title = (existence.matched_title or reference.title or "").lower()
    title_found = False
    if expected_title and len(expected_title) > 10:
        norm_title = " ".join(expected_title.split())
        if norm_title in text_lower:
            # Verify it's not a substring of a longer, different title.
            # Find where the title appears and check surrounding context.
            idx = text_lower.find(norm_title)
            if idx >= 0:
                # Check that the match isn't embedded in a longer title
                # by looking at characters before/after the match
                before = text_lower[max(0, idx - 1):idx]
                after_idx = idx + len(norm_title)
                after = text_lower[after_idx:after_idx + 1] if after_idx < len(text_lower) else ""
                # If surrounded by word characters, it might be part of a longer title
                if before.isalpha() or after.isalpha():
                    # Longer title — check if the full surrounding phrase is very different
                    # Extract a window around the match
                    window_start = max(0, idx - 30)
                    window_end = min(len(text_lower), after_idx + 30)
                    window = text_lower[window_start:window_end]
                    # If the window is much longer than our title, be suspicious
                    pass  # fall through to author check for confirmation
                else:
                    title_found = True
        # Try partial match — first 60 chars of title (handles subtitle truncation)
        if not title_found:
            short_title = norm_title[:60]
            if len(short_title) > 20 and short_title in text_lower:
                title_found = True

    # Check for author last name presence (at least one)
    author_found = False
    if reference.authors:
        for author in reference.authors[:3]:  # check first 3 authors
            parts = author.strip().split()
            if parts:
                last_name = parts[0].rstrip(",").lower() if "," in author else parts[-1].lower()
                if len(last_name) > 2 and last_name in text_lower:
                    author_found = True
                    break

    # Both title and author = strong match
    if title_found and author_found:
        return True
    # Title alone is sufficient if it's long/specific enough (>40 chars)
    if title_found and len(expected_title) > 40:
        return True
    # Author alone is sufficient (title might not appear verbatim in the text)
    if author_found:
        return True

    logger.info(
        "Content validation failed for '%s' — text does not contain expected title or authors",
        expected_title[:50],
    )
    return False


def _looks_like_paper(text: str) -> bool:
    """Check if text looks like actual paper content vs a landing page or listing.

    Rejects short text, document listings, cookie notices, etc.
    """
    if len(text) < 2000:
        return False

    text_lower = text[:5000].lower()

    # Reject common landing page / junk indicators
    junk_signals = [
        "accept cookies",
        "cookie policy",
        "sign in to access",
        "purchase this article",
        "add to cart",
        "subscribe to access",
    ]
    junk_count = sum(1 for s in junk_signals if s in text_lower)
    if junk_count >= 2:
        return False

    # Should have paragraph-length content (not just a list of links)
    # Count sentences (rough heuristic: periods followed by space+uppercase or newline)
    sentences = text.count(". ") + text.count(".\n")
    if sentences < 10:
        return False

    return True


def _fuzzy_match_filename(filename: str, title: str, doi: str) -> bool:
    """Check if a PDF filename fuzzy-matches a reference title or contains the DOI."""
    stem = Path(filename).stem.lower()

    # Check DOI match (replace / with _ or - as common in filenames)
    if doi:
        doi_lower = doi.lower()
        doi_variants = [doi_lower, doi_lower.replace("/", "_"), doi_lower.replace("/", "-")]
        for variant in doi_variants:
            if variant in stem:
                return True

    # Fuzzy title match
    if title:
        title_lower = title.lower()
        # Normalize both for comparison
        norm_stem = "".join(c for c in stem if c.isalnum() or c.isspace())
        norm_title = "".join(c for c in title_lower if c.isalnum() or c.isspace())
        ratio = SequenceMatcher(None, norm_stem, norm_title).ratio()
        if ratio > 0.6:
            return True

    return False


def _find_user_pdf(refs_dir: str, reference: Reference) -> Path | None:
    """Search refs_dir for a PDF matching the reference by title or DOI."""
    if not refs_dir:
        return None

    refs_path = Path(refs_dir)
    if not refs_path.is_dir():
        return None

    for pdf_file in refs_path.glob("*.pdf"):
        if _fuzzy_match_filename(pdf_file.name, reference.title, reference.doi):
            return pdf_file

    return None


def _extract_pdf_text_sync(pdf_path: Path) -> str:
    """Extract text from a local PDF file."""
    try:
        doc = pymupdf.open(str(pdf_path))
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        doc.close()
        return "\n\n".join(pages)[:50_000]
    except Exception:
        logger.warning("Failed to extract text from %s", pdf_path)
        return ""


async def _get_source_content(
    existence: ExistenceResult,
    reference: Reference,
    *,
    refs_dir: str = "",
    arxiv: ArxivAPI | None = None,
    unpaywall: UnpaywallAPI | None = None,
    doi_resolver: DOIResolver | None = None,
    semantic_scholar: SemanticScholarAPI | None = None,
    google_scholar: GoogleScholarAPI | None = None,
) -> tuple[str, str, str, list[str]]:
    """Get source content for verification.

    Returns (content, source_type, source_via, sources_tried).
    Tries sources in priority order, stops at first success.
    """
    sources_tried: list[str] = []

    # 1. User-supplied PDF (highest priority)
    if refs_dir:
        sources_tried.append("refs_dir")
        pdf_path = await asyncio.to_thread(_find_user_pdf, refs_dir, reference)
        if pdf_path:
            text = await asyncio.to_thread(_extract_pdf_text_sync, pdf_path)
            if text:
                return text, "full_text", "refs_dir", sources_tried

    # 2. arXiv — free full text for preprints
    if arxiv is not None and existence.matched_title:
        sources_tried.append("arxiv")
        try:
            results = await arxiv.search_by_title(existence.matched_title, max_results=3)
            for r in results:
                if r.get("title"):
                    ratio = SequenceMatcher(
                        None,
                        existence.matched_title.lower(),
                        r["title"].lower(),
                    ).ratio()
                    if ratio > _ARXIV_TITLE_THRESHOLD and r.get("pdf_url"):
                        text = await arxiv.fetch_full_text(r["pdf_url"])
                        if text and _validate_content(text, reference, existence):
                            return text, "full_text", "arxiv", sources_tried
                        elif text:
                            logger.info("arXiv PDF failed content validation for '%s'", existence.matched_title[:50])
        except (APIError, Exception) as e:
            logger.debug("arXiv retrieval failed: %s", e)

    # 3. Unpaywall — open-access full text via DOI
    if unpaywall is not None and existence.matched_doi:
        sources_tried.append("unpaywall")
        pdf_url = await unpaywall.get_oa_pdf_url(existence.matched_doi)
        if pdf_url:
            text = await _fetch_full_text(pdf_url)
            if text and _validate_content(text, reference, existence):
                return text, "full_text", "unpaywall", sources_tried
            elif text:
                logger.info("Unpaywall content failed validation for '%s'", existence.matched_title[:50])

    # 4. DOI direct resolution — follow DOI link, grab HTML/PDF
    if doi_resolver is not None and existence.matched_doi:
        sources_tried.append("doi_resolver")
        text = await doi_resolver.resolve_full_text(existence.matched_doi)
        if text and _looks_like_paper(text) and _validate_content(text, reference, existence):
            return text, "full_text", "doi_resolver", sources_tried
        elif text:
            logger.info("DOI resolver content failed validation for '%s'", existence.matched_title[:50])

    # 5. Semantic Scholar abstract — fallback
    if semantic_scholar is not None and existence.matched_doi:
        sources_tried.append("semantic_scholar")
        try:
            data = await semantic_scholar.get_by_doi(existence.matched_doi)
            abstract = data.get("abstract", "")
            if abstract:
                return abstract, "abstract", "semantic_scholar", sources_tried
        except APIError:
            pass

    # 6. Google Scholar abstract — last resort
    if google_scholar is not None and existence.matched_title:
        sources_tried.append("google_scholar")
        try:
            results = await google_scholar.search_by_title(existence.matched_title, limit=1)
            if results:
                abstract = results[0].get("abstract", "")
                if abstract and len(abstract) > 50:
                    return abstract, "abstract", "google_scholar", sources_tried
        except APIError:
            pass

    return "", "", "", sources_tried


async def _fetch_full_text(url: str) -> str:
    """Fetch full text from a URL, handling both HTML and PDF."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return ""

            content_type = resp.headers.get("content-type", "")

            # Handle PDF
            if "pdf" in content_type or url.endswith(".pdf"):
                try:
                    doc = pymupdf.open(stream=resp.content, filetype="pdf")
                    pages = []
                    for page in doc:
                        text = page.get_text()
                        if text.strip():
                            pages.append(text)
                    doc.close()
                    full = "\n\n".join(pages)
                    return full[:50_000]
                except Exception:
                    logger.warning("Failed to parse PDF from %s", url)
                    return ""

            # Handle HTML
            text = resp.text[:50_000]
            if len(text) > 500:
                return text

    except Exception:
        logger.warning("Failed to fetch full text from %s", url)

    return ""


async def verify_claim(
    citation: InTextCitation,
    existence: ExistenceResult,
    reference: Reference,
    *,
    llm: LLMClient,
    model: str,
    refs_dir: str = "",
    arxiv: ArxivAPI | None = None,
    unpaywall: UnpaywallAPI | None = None,
    doi_resolver: DOIResolver | None = None,
    semantic_scholar: SemanticScholarAPI | None = None,
    google_scholar: GoogleScholarAPI | None = None,
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

    source_content, source_type, source_via, sources_tried = await _get_source_content(
        existence,
        reference,
        refs_dir=refs_dir,
        arxiv=arxiv,
        unpaywall=unpaywall,
        doi_resolver=doi_resolver,
        semantic_scholar=semantic_scholar,
        google_scholar=google_scholar,
    )

    if not source_content:
        return ClaimVerificationResult(
            claim=citation.claim_made,
            supported=None,
            confidence=0.0,
            explanation="No source content available for verification",
            source_type="",
            source_via="",
            sources_tried=sources_tried,
        )

    user_message = (
        f"## Claim made in the citing paper\n{citation.claim_made}\n\n"
        f"## Citation context\n{citation.surrounding_text}\n\n"
        f"## Source material ({source_type} via {source_via})\n{source_content}"
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
        source_via=source_via,
        sources_tried=sources_tried,
    )
