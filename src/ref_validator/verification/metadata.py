"""Level 2: Verify metadata accuracy."""

import difflib
import logging
from typing import Any

from ref_validator.apis.crossref import CrossRefAPI
from ref_validator.apis.semantic_scholar import SemanticScholarAPI
from ref_validator.errors import APIError
from ref_validator.models.citation import Reference
from ref_validator.models.verification import ExistenceResult, MetadataResult

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    return s.lower().strip()


def _extract_last_name(author: str) -> str:
    """Extract last name from an author string, handling common formats."""
    author = author.strip().rstrip(".")
    if not author:
        return ""

    # "Last, First" or "Last, F." format
    if "," in author:
        return author.split(",")[0].strip().lower()

    parts = author.split()
    if not parts:
        return ""

    # Skip suffixes like Jr., Sr., III, IV
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    last = parts[-1].rstrip(".").lower()
    if last in suffixes and len(parts) > 1:
        last = parts[-2].rstrip(".").lower()

    return last


def _last_names(authors: list[str]) -> set[str]:
    """Extract last names from author strings."""
    names = set()
    for a in authors:
        name = _extract_last_name(a)
        if name:
            names.add(name)
    return names


def _extract_crossref_authors(item: dict) -> list[str]:
    authors = item.get("author", [])
    return [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors]


def _extract_crossref_year(item: dict) -> int | None:
    dp = item.get("published-print") or item.get("published-online") or item.get("created")
    if dp:
        parts = dp.get("date-parts", [[]])
        if parts and parts[0]:
            return parts[0][0]
    return None


def _extract_crossref_venue(item: dict) -> str:
    ct = item.get("container-title", [])
    return ct[0] if ct else ""


def _extract_ss_authors(item: dict) -> list[str]:
    return [a.get("name", "") for a in item.get("authors", [])]


async def check_metadata(
    reference: Reference,
    existence: ExistenceResult,
    *,
    crossref: CrossRefAPI | None = None,
    semantic_scholar: SemanticScholarAPI | None = None,
) -> MetadataResult:
    """Compare reference metadata against API data."""
    if not existence.found:
        return MetadataResult(issues=["Cannot check metadata: paper not found"])

    api_data = await _fetch_api_data(existence, crossref=crossref, semantic_scholar=semantic_scholar)
    if api_data is None:
        return MetadataResult(issues=["Could not fetch metadata from API"])

    issues: list[str] = []
    matched_fields: dict[str, str] = {}

    # Title match — reliable, used for verification status
    api_title = api_data.get("title", "")
    title_match = False
    if reference.title and api_title:
        sim = difflib.SequenceMatcher(None, _normalize(reference.title), _normalize(api_title)).ratio()
        title_match = sim >= 0.85
        matched_fields["title"] = api_title
        if not title_match:
            issues.append(f"Title mismatch: '{reference.title}' vs '{api_title}' (similarity: {sim:.2f})")

    # Authors match — informational only, API author data is often unreliable
    api_authors = api_data.get("authors", [])
    authors_match = False
    if reference.authors and api_authors:
        ref_names = _last_names(reference.authors)
        api_names = _last_names(api_authors)
        if ref_names and api_names:
            matched = 0
            for rn in ref_names:
                for an in api_names:
                    if rn == an or difflib.SequenceMatcher(None, rn, an).ratio() >= 0.8:
                        matched += 1
                        break
            overlap = matched / max(len(ref_names), len(api_names))
            authors_match = overlap >= 0.5
            matched_fields["authors"] = ", ".join(api_authors)
            if not authors_match:
                logger.info("Author data differs (may be API data quality issue): ref=%s vs api=%s", ref_names, api_names)

    # Year match (±1 tolerance) — reliable, used for verification status
    api_year = api_data.get("year")
    year_match = False
    if reference.year is not None and api_year is not None:
        year_match = abs(reference.year - api_year) <= 1
        matched_fields["year"] = str(api_year)
        if not year_match:
            issues.append(f"Year mismatch: {reference.year} vs {api_year}")
    elif reference.year is None or api_year is None:
        # Don't penalize if year is missing from either side
        year_match = True

    # Venue match — informational only, API venue data varies widely
    api_venue = api_data.get("venue", "")
    venue_match = False
    if reference.venue and api_venue:
        sim = difflib.SequenceMatcher(None, _normalize(reference.venue), _normalize(api_venue)).ratio()
        venue_match = sim >= 0.6
        matched_fields["venue"] = api_venue
        if not venue_match:
            logger.info("Venue data differs (may be API data quality issue): '%s' vs '%s'", reference.venue, api_venue)

    return MetadataResult(
        title_match=title_match,
        authors_match=authors_match,
        year_match=year_match,
        venue_match=venue_match,
        matched_fields=matched_fields,
        issues=issues,
    )


async def _fetch_api_data(
    existence: ExistenceResult,
    *,
    crossref: CrossRefAPI | None = None,
    semantic_scholar: SemanticScholarAPI | None = None,
) -> dict[str, Any] | None:
    """Fetch detailed metadata from the API that found the paper."""
    if crossref is not None and existence.source_api == "crossref" and existence.matched_doi:
        try:
            item = await crossref.get_by_doi(existence.matched_doi)
            return {
                "title": (_extract_title(item)),
                "authors": _extract_crossref_authors(item),
                "year": _extract_crossref_year(item),
                "venue": _extract_crossref_venue(item),
            }
        except APIError:
            pass

    if semantic_scholar is not None and existence.matched_doi:
        try:
            item = await semantic_scholar.get_by_doi(existence.matched_doi)
            return {
                "title": item.get("title", ""),
                "authors": _extract_ss_authors(item),
                "year": item.get("year"),
                "venue": item.get("venue", ""),
            }
        except APIError:
            pass

    # Fallback: use what we already have from existence check
    if existence.matched_title:
        return {"title": existence.matched_title, "authors": [], "year": None, "venue": ""}

    return None


def _extract_title(item: dict) -> str:
    titles = item.get("title", [])
    if isinstance(titles, list):
        return titles[0] if titles else ""
    return str(titles)
