"""Tests for the arXiv API client."""

import pytest
import httpx
import respx

from ref_validator.apis.arxiv import ArxivAPI, ARXIV_API_URL

SAMPLE_ATOM_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>Attention Is All You Need</title>
    <link title="pdf" href="https://arxiv.org/pdf/2301.12345v1" rel="related" type="application/pdf"/>
    <summary>We propose a new architecture...</summary>
  </entry>
</feed>
"""

SAMPLE_EMPTY_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>
"""


@pytest.fixture
def arxiv_client():
    return ArxivAPI(timeout=5.0)


@respx.mock
async def test_search_by_title_returns_results(arxiv_client):
    respx.get(ARXIV_API_URL).mock(
        return_value=httpx.Response(200, text=SAMPLE_ATOM_RESPONSE)
    )

    results = await arxiv_client.search_by_title("Attention Is All You Need")
    assert len(results) == 1
    assert results[0]["title"] == "Attention Is All You Need"
    assert results[0]["pdf_url"] == "https://arxiv.org/pdf/2301.12345v1"
    assert "2301.12345" in results[0]["arxiv_id"]

    await arxiv_client.close()


@respx.mock
async def test_search_by_title_empty_results(arxiv_client):
    respx.get(ARXIV_API_URL).mock(
        return_value=httpx.Response(200, text=SAMPLE_EMPTY_RESPONSE)
    )

    results = await arxiv_client.search_by_title("Nonexistent Paper Title XYZ")
    assert results == []

    await arxiv_client.close()


@respx.mock
async def test_search_by_title_api_error(arxiv_client):
    respx.get(ARXIV_API_URL).mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(Exception):
        await arxiv_client.search_by_title("test")

    await arxiv_client.close()


@respx.mock
async def test_fetch_full_text_returns_empty_on_failure(arxiv_client):
    respx.get("https://arxiv.org/pdf/2301.12345v1").mock(
        return_value=httpx.Response(404)
    )

    text = await arxiv_client.fetch_full_text("https://arxiv.org/pdf/2301.12345v1")
    assert text == ""

    await arxiv_client.close()


@respx.mock
async def test_search_parses_id_fallback_pdf_url():
    """When no explicit pdf link, derive from arxiv ID."""
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2405.99999v2</id>
    <title>Some Paper</title>
  </entry>
</feed>
"""
    client = ArxivAPI(timeout=5.0)
    respx.get(ARXIV_API_URL).mock(
        return_value=httpx.Response(200, text=xml)
    )

    results = await client.search_by_title("Some Paper")
    assert len(results) == 1
    assert results[0]["pdf_url"] == "https://arxiv.org/pdf/2405.99999v2"

    await client.close()


async def test_check_connectivity_success():
    client = ArxivAPI(timeout=5.0)
    with respx.mock:
        respx.get(ARXIV_API_URL).mock(
            return_value=httpx.Response(200, text=SAMPLE_EMPTY_RESPONSE)
        )
        result = await client.check_connectivity()
        assert result is True

    await client.close()
