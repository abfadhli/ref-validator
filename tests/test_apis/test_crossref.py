"""Tests for CrossRef API client."""

import httpx
import pytest
import respx

from ref_validator.apis.crossref import CrossRefAPI


@pytest.fixture
def crossref():
    return CrossRefAPI(mailto="test@example.com", timeout=5.0)


@pytest.mark.asyncio
@respx.mock
async def test_search_by_title(crossref):
    respx.get("https://api.crossref.org/works").mock(
        return_value=httpx.Response(200, json={
            "message": {
                "items": [
                    {
                        "DOI": "10.1234/test",
                        "title": ["A test paper"],
                        "author": [{"given": "John", "family": "Smith"}],
                    }
                ]
            }
        })
    )
    results = await crossref.search_by_title("A test paper")
    assert len(results) == 1
    assert results[0]["DOI"] == "10.1234/test"


@pytest.mark.asyncio
@respx.mock
async def test_get_by_doi(crossref):
    respx.get("https://api.crossref.org/works/10.1234/test").mock(
        return_value=httpx.Response(200, json={
            "message": {
                "DOI": "10.1234/test",
                "title": ["A test paper"],
            }
        })
    )
    result = await crossref.get_by_doi("10.1234/test")
    assert result["DOI"] == "10.1234/test"


@pytest.mark.asyncio
@respx.mock
async def test_check_connectivity(crossref):
    respx.get("https://api.crossref.org/works").mock(
        return_value=httpx.Response(200, json={"message": {"items": []}})
    )
    assert await crossref.check_connectivity() is True
