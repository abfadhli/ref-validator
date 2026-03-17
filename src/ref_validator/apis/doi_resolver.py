"""DOI direct resolution — follow DOI links to grab HTML or PDF full text."""

import logging
import re

import httpx
import pymupdf

logger = logging.getLogger(__name__)


class DOIResolver:
    """Follow DOI URLs to retrieve full text from open publisher pages."""

    API_NAME = "doi_resolver"

    def __init__(self, *, timeout: float = 30.0):
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"Accept": "text/html"},
        )

    async def resolve_full_text(self, doi: str) -> str:
        """Follow a DOI URL and try to extract full text.

        Handles two cases:
        1. Response is HTML with substantial body text (>1000 chars)
        2. Response redirects to or contains a PDF link
        """
        doi_url = doi if doi.startswith("http") else f"https://doi.org/{doi}"

        try:
            resp = await self._client.get(doi_url)
            if resp.status_code != 200:
                return ""
        except httpx.HTTPError as e:
            logger.debug("DOI resolution failed for %s: %s", doi, e)
            return ""

        content_type = resp.headers.get("content-type", "")

        # If we landed on a PDF
        if "pdf" in content_type:
            return self._extract_pdf_text(resp.content)

        # If we got HTML, try to extract body text
        if "html" in content_type:
            text = self._extract_html_text(resp.text)
            if len(text) > 1000:
                return text[:50_000]

        return ""

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            pages = []
            for page in doc:
                text = page.get_text()
                if text.strip():
                    pages.append(text)
            doc.close()
            full = "\n\n".join(pages)
            return full[:50_000]
        except Exception:
            logger.warning("Failed to parse PDF from DOI resolution")
            return ""

    def _extract_html_text(self, html: str) -> str:
        """Extract readable text from HTML, stripping tags."""
        try:
            from lxml import etree
            from lxml.html import fromstring as html_fromstring

            doc = html_fromstring(html)
            # Remove script and style elements
            for el in doc.iter("script", "style", "nav", "header", "footer"):
                el.getparent().remove(el)
            text = doc.text_content()
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()
            return text
        except ImportError:
            # Fallback: basic tag stripping without lxml
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text

    async def close(self) -> None:
        await self._client.aclose()
