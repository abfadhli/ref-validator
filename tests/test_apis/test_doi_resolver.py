"""Tests for the DOI resolver."""

import pytest
import httpx
import respx

from ref_validator.apis.doi_resolver import DOIResolver


@pytest.fixture
def resolver():
    return DOIResolver(timeout=5.0)


@respx.mock
async def test_resolve_html_full_text(resolver):
    body = "<html><body>" + "This is a long article. " * 100 + "</body></html>"
    respx.get("https://doi.org/10.1234/test").mock(
        return_value=httpx.Response(200, text=body, headers={"content-type": "text/html"})
    )

    text = await resolver.resolve_full_text("10.1234/test")
    assert len(text) > 1000
    assert "long article" in text

    await resolver.close()


@respx.mock
async def test_resolve_short_html_returns_empty(resolver):
    respx.get("https://doi.org/10.1234/short").mock(
        return_value=httpx.Response(200, text="<html><body>Short</body></html>", headers={"content-type": "text/html"})
    )

    text = await resolver.resolve_full_text("10.1234/short")
    assert text == ""

    await resolver.close()


@respx.mock
async def test_resolve_404_returns_empty(resolver):
    respx.get("https://doi.org/10.1234/missing").mock(
        return_value=httpx.Response(404)
    )

    text = await resolver.resolve_full_text("10.1234/missing")
    assert text == ""

    await resolver.close()


@respx.mock
async def test_resolve_network_error_returns_empty(resolver):
    respx.get("https://doi.org/10.1234/fail").mock(side_effect=httpx.ConnectError("fail"))

    text = await resolver.resolve_full_text("10.1234/fail")
    assert text == ""

    await resolver.close()
