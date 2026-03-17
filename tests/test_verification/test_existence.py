"""Tests for existence verification."""

from unittest.mock import AsyncMock

import pytest

from ref_validator.apis.crossref import CrossRefAPI
from ref_validator.apis.openalex import OpenAlexAPI
from ref_validator.apis.semantic_scholar import SemanticScholarAPI
from ref_validator.models.citation import Reference
from ref_validator.verification.existence import check_existence, _fuzzy_title_match


def test_fuzzy_title_match_exact():
    assert _fuzzy_title_match("Hello World", "Hello World") == 1.0


def test_fuzzy_title_match_case_insensitive():
    assert _fuzzy_title_match("Hello World", "hello world") == 1.0


def test_fuzzy_title_match_different():
    score = _fuzzy_title_match("Hello World", "Goodbye Universe")
    assert score < 0.5


@pytest.mark.asyncio
async def test_check_existence_by_doi(sample_reference):
    crossref = AsyncMock(spec=CrossRefAPI)
    crossref.get_by_doi = AsyncMock(return_value={
        "title": ["A great paper"],
        "DOI": "10.1038/s41586-020-0001-1",
    })
    semantic_scholar = AsyncMock(spec=SemanticScholarAPI)
    openalex = AsyncMock(spec=OpenAlexAPI)

    result = await check_existence(
        sample_reference,
        crossref=crossref,
        semantic_scholar=semantic_scholar,
        openalex=openalex,
    )
    assert result.found is True
    assert result.source_api == "crossref"


@pytest.mark.asyncio
async def test_check_existence_by_title(sample_reference):
    sample_reference.doi = ""

    crossref = AsyncMock(spec=CrossRefAPI)
    crossref.search_by_title = AsyncMock(return_value=[
        {"title": ["A great paper"], "DOI": "10.1038/found"}
    ])
    semantic_scholar = AsyncMock(spec=SemanticScholarAPI)
    semantic_scholar.search_by_title = AsyncMock(return_value=[])
    openalex = AsyncMock(spec=OpenAlexAPI)
    openalex.search_by_title = AsyncMock(return_value=[])

    result = await check_existence(
        sample_reference,
        crossref=crossref,
        semantic_scholar=semantic_scholar,
        openalex=openalex,
    )
    assert result.found is True
    assert result.matched_doi == "10.1038/found"


@pytest.mark.asyncio
async def test_check_existence_not_found():
    ref = Reference(ref_id="99", raw_text="Fake paper", title="Nonexistent paper")

    crossref = AsyncMock(spec=CrossRefAPI)
    crossref.search_by_title = AsyncMock(return_value=[])
    semantic_scholar = AsyncMock(spec=SemanticScholarAPI)
    semantic_scholar.search_by_title = AsyncMock(return_value=[])
    openalex = AsyncMock(spec=OpenAlexAPI)
    openalex.search_by_title = AsyncMock(return_value=[])

    result = await check_existence(
        ref,
        crossref=crossref,
        semantic_scholar=semantic_scholar,
        openalex=openalex,
    )
    assert result.found is False
