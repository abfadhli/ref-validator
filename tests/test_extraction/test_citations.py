"""Tests for LLM-based citation extraction."""

from unittest.mock import AsyncMock, patch

import pytest

from ref_validator.extraction.citations import extract_citations
from ref_validator.llm.client import LLMClient


@pytest.fixture
def mock_llm():
    llm = AsyncMock(spec=LLMClient)
    llm.extract_structured = AsyncMock(return_value={
        "references": [
            {
                "ref_id": "1",
                "raw_text": "Smith, J. (2020). Test paper. Nature, 580, 100.",
                "title": "Test paper",
                "authors": ["J. Smith"],
                "year": 2020,
                "venue": "Nature",
                "doi": "10.1038/test",
                "volume": "580",
                "pages": "100",
                "url": "",
            }
        ],
        "in_text_citations": [
            {
                "ref_id": "1",
                "marker": "[1]",
                "surrounding_text": "As shown by Smith [1], the effect is significant.",
                "claim_made": "the effect is significant",
            }
        ],
    })
    return llm


@pytest.mark.asyncio
async def test_extract_citations(mock_llm):
    result = await extract_citations("Some paper text", mock_llm, "claude-sonnet-4-6")

    assert len(result.references) == 1
    assert result.references[0].ref_id == "1"
    assert result.references[0].title == "Test paper"
    assert result.references[0].year == 2020

    assert len(result.in_text_citations) == 1
    assert result.in_text_citations[0].claim_made == "the effect is significant"

    assert "1" in result.citation_map
    assert len(result.citation_map["1"]) == 1


@pytest.mark.asyncio
async def test_extract_citations_empty(mock_llm):
    mock_llm.extract_structured.return_value = {
        "references": [],
        "in_text_citations": [],
    }
    result = await extract_citations("Empty paper", mock_llm, "claude-sonnet-4-6")
    assert len(result.references) == 0
    assert len(result.in_text_citations) == 0
