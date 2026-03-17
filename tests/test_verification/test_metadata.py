"""Tests for metadata verification."""

from unittest.mock import AsyncMock

import pytest

from ref_validator.apis.crossref import CrossRefAPI
from ref_validator.apis.semantic_scholar import SemanticScholarAPI
from ref_validator.models.verification import ExistenceResult
from ref_validator.verification.metadata import check_metadata, _last_names, _extract_last_name


def test_last_names():
    assert _last_names(["John Smith", "Jane Doe"]) == {"smith", "doe"}


def test_last_names_single():
    assert _last_names(["Smith"]) == {"smith"}


def test_last_names_comma_format():
    """'Last, First' format common in bibliographies."""
    assert _last_names(["Smith, John", "Doe, Jane"]) == {"smith", "doe"}


def test_last_names_suffix():
    """Names with Jr., Sr., etc."""
    assert _extract_last_name("John Smith Jr.") == "smith"
    assert _extract_last_name("Robert Jones III") == "jones"


def test_last_names_initial_format():
    """'J. Smith' or 'J.A. Smith' format."""
    assert _last_names(["J. Smith", "A.B. Doe"]) == {"smith", "doe"}


def test_last_names_comma_with_initials():
    """'Smith, J.' or 'Smith, J.A.' format."""
    assert _last_names(["Smith, J.", "Doe, J.A."]) == {"smith", "doe"}


@pytest.mark.asyncio
async def test_check_metadata_matching(sample_reference, found_existence):
    crossref = AsyncMock(spec=CrossRefAPI)
    crossref.get_by_doi = AsyncMock(return_value={
        "title": ["A great paper"],
        "author": [{"given": "John", "family": "Smith"}],
        "published-print": {"date-parts": [[2020]]},
        "container-title": ["Nature"],
    })
    semantic_scholar = AsyncMock(spec=SemanticScholarAPI)

    result = await check_metadata(
        sample_reference, found_existence,
        crossref=crossref,
        semantic_scholar=semantic_scholar,
    )
    assert result.title_match is True
    assert result.authors_match is True
    assert result.year_match is True
    assert result.venue_match is True
    assert len(result.issues) == 0


@pytest.mark.asyncio
async def test_check_metadata_year_tolerance(sample_reference, found_existence):
    crossref = AsyncMock(spec=CrossRefAPI)
    crossref.get_by_doi = AsyncMock(return_value={
        "title": ["A great paper"],
        "author": [{"given": "John", "family": "Smith"}],
        "published-print": {"date-parts": [[2021]]},  # off by 1
        "container-title": ["Nature"],
    })
    semantic_scholar = AsyncMock(spec=SemanticScholarAPI)

    result = await check_metadata(
        sample_reference, found_existence,
        crossref=crossref,
        semantic_scholar=semantic_scholar,
    )
    assert result.year_match is True  # ±1 tolerance


@pytest.mark.asyncio
async def test_check_metadata_not_found():
    existence = ExistenceResult(found=False)
    crossref = AsyncMock(spec=CrossRefAPI)
    semantic_scholar = AsyncMock(spec=SemanticScholarAPI)

    from ref_validator.models.citation import Reference
    ref = Reference(ref_id="1", raw_text="test", title="test")

    result = await check_metadata(
        ref, existence,
        crossref=crossref,
        semantic_scholar=semantic_scholar,
    )
    assert "Cannot check metadata" in result.issues[0]
