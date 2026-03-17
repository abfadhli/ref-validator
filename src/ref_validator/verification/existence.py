"""Level 1: Verify that a referenced paper exists."""

import asyncio
import difflib
import logging

from ref_validator.apis.crossref import CrossRefAPI
from ref_validator.apis.google_scholar import GoogleScholarAPI
from ref_validator.apis.openalex import OpenAlexAPI
from ref_validator.apis.semantic_scholar import SemanticScholarAPI
from ref_validator.errors import APIError
from ref_validator.models.citation import Reference
from ref_validator.models.verification import ExistenceResult

logger = logging.getLogger(__name__)


def _fuzzy_title_match(title_a: str, title_b: str) -> float:
    """Compute fuzzy similarity between two titles."""
    a = title_a.lower().strip()
    b = title_b.lower().strip()
    return difflib.SequenceMatcher(None, a, b).ratio()


def _extract_title_from_crossref(item: dict) -> str:
    titles = item.get("title", [])
    return titles[0] if titles else ""


def _extract_title_from_openalex(item: dict) -> str:
    return item.get("title", "") or item.get("display_name", "") or ""


async def check_existence(
    reference: Reference,
    *,
    crossref: CrossRefAPI | None = None,
    semantic_scholar: SemanticScholarAPI | None = None,
    openalex: OpenAlexAPI | None = None,
    google_scholar: GoogleScholarAPI | None = None,
    threshold: float = 0.85,
) -> ExistenceResult:
    """Check if a reference exists by searching academic APIs."""
    # Fast path: DOI lookup
    if reference.doi:
        result = await _check_by_doi(
            reference, crossref=crossref, semantic_scholar=semantic_scholar, threshold=threshold
        )
        if result.found:
            return result

    if not reference.title:
        return ExistenceResult(issues=["No title or DOI available for search"])

    # Search all enabled APIs in parallel by title
    search_tasks = []
    if crossref is not None:
        search_tasks.append(_search_crossref(reference, crossref, threshold))
    if semantic_scholar is not None:
        search_tasks.append(_search_semantic_scholar(reference, semantic_scholar, threshold))
    if openalex is not None:
        search_tasks.append(_search_openalex(reference, openalex, threshold))
    if google_scholar is not None:
        search_tasks.append(_search_google_scholar(reference, google_scholar, threshold))

    if not search_tasks:
        return ExistenceResult(found=False, issues=["No API sources enabled"])

    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    # Return best match
    best: ExistenceResult | None = None
    for r in results:
        if isinstance(r, Exception):
            logger.warning("API search failed: %s", r)
            continue
        if r.found and (best is None or r.title_similarity > best.title_similarity):
            best = r

    if best:
        return best

    return ExistenceResult(
        found=False,
        issues=[f"Paper not found in any API: '{reference.title}'"],
    )


async def _check_by_doi(
    reference: Reference,
    *,
    crossref: CrossRefAPI | None,
    semantic_scholar: SemanticScholarAPI | None,
    threshold: float,
) -> ExistenceResult:
    """Try to look up by DOI directly."""
    if crossref is not None:
        try:
            data = await crossref.get_by_doi(reference.doi)
            cr_title = _extract_title_from_crossref(data)
            if cr_title:
                sim = _fuzzy_title_match(reference.title, cr_title) if reference.title else 1.0
                return ExistenceResult(
                    found=True,
                    source_api="crossref",
                    matched_doi=reference.doi,
                    matched_title=cr_title,
                    title_similarity=sim,
                )
        except APIError:
            pass

    if semantic_scholar is not None:
        try:
            data = await semantic_scholar.get_by_doi(reference.doi)
            ss_title = data.get("title", "")
            if ss_title:
                sim = _fuzzy_title_match(reference.title, ss_title) if reference.title else 1.0
                return ExistenceResult(
                    found=True,
                    source_api="semantic_scholar",
                    matched_doi=reference.doi,
                    matched_title=ss_title,
                    title_similarity=sim,
                )
        except APIError:
            pass

    return ExistenceResult(found=False, issues=[f"DOI {reference.doi} not found"])


async def _search_crossref(
    reference: Reference, api: CrossRefAPI, threshold: float
) -> ExistenceResult:
    try:
        items = await api.search_by_title(reference.title)
    except APIError as e:
        return ExistenceResult(issues=[f"CrossRef search failed: {e}"])

    for item in items:
        cr_title = _extract_title_from_crossref(item)
        if not cr_title:
            continue
        sim = _fuzzy_title_match(reference.title, cr_title)
        if sim >= threshold:
            return ExistenceResult(
                found=True,
                source_api="crossref",
                matched_doi=item.get("DOI", ""),
                matched_title=cr_title,
                title_similarity=sim,
            )
    return ExistenceResult(found=False)


async def _search_semantic_scholar(
    reference: Reference, api: SemanticScholarAPI, threshold: float
) -> ExistenceResult:
    try:
        items = await api.search_by_title(reference.title)
    except APIError as e:
        return ExistenceResult(issues=[f"Semantic Scholar search failed: {e}"])

    for item in items:
        ss_title = item.get("title", "")
        if not ss_title:
            continue
        sim = _fuzzy_title_match(reference.title, ss_title)
        if sim >= threshold:
            doi = ""
            ext_ids = item.get("externalIds", {})
            if ext_ids:
                doi = ext_ids.get("DOI", "")
            return ExistenceResult(
                found=True,
                source_api="semantic_scholar",
                matched_doi=doi,
                matched_title=ss_title,
                title_similarity=sim,
            )
    return ExistenceResult(found=False)


async def _search_openalex(
    reference: Reference, api: OpenAlexAPI, threshold: float
) -> ExistenceResult:
    try:
        items = await api.search_by_title(reference.title)
    except APIError as e:
        return ExistenceResult(issues=[f"OpenAlex search failed: {e}"])

    for item in items:
        oa_title = _extract_title_from_openalex(item)
        if not oa_title:
            continue
        sim = _fuzzy_title_match(reference.title, oa_title)
        if sim >= threshold:
            doi = item.get("doi", "") or ""
            if doi.startswith("https://doi.org/"):
                doi = doi[len("https://doi.org/"):]
            return ExistenceResult(
                found=True,
                source_api="openalex",
                matched_doi=doi,
                matched_title=oa_title,
                title_similarity=sim,
            )
    return ExistenceResult(found=False)


async def _search_google_scholar(
    reference: Reference, api: GoogleScholarAPI, threshold: float
) -> ExistenceResult:
    try:
        items = await api.search_by_title(reference.title)
    except APIError as e:
        return ExistenceResult(issues=[f"Google Scholar search failed: {e}"])

    for item in items:
        gs_title = item.get("title", "")
        if not gs_title:
            continue
        sim = _fuzzy_title_match(reference.title, gs_title)
        if sim >= threshold:
            return ExistenceResult(
                found=True,
                source_api="google_scholar",
                matched_doi="",
                matched_title=gs_title,
                title_similarity=sim,
            )
    return ExistenceResult(found=False)
