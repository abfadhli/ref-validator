"""arXiv API client for searching papers and fetching full text PDFs."""

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import pymupdf

from ref_validator.errors import APIError

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivAPI:
    """arXiv API client for paper search and full-text retrieval."""

    API_NAME = "arxiv"

    def __init__(self, *, timeout: float = 30.0):
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def search_by_title(self, title: str, max_results: int = 3) -> list[dict[str, Any]]:
        """Search arXiv by title. Returns list of results with id, title, pdf_url."""
        query = f'ti:"{title}"'
        try:
            resp = await self._client.get(
                ARXIV_API_URL,
                params={"search_query": query, "max_results": max_results},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise APIError(f"arXiv search failed: {e}", api_name=self.API_NAME) from e

        return self._parse_feed(resp.text)

    def _parse_feed(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse Atom feed from arXiv API response."""
        results: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("Failed to parse arXiv XML response")
            return results

        for entry in root.findall("atom:entry", ARXIV_NS):
            arxiv_id = (entry.findtext("atom:id", "", ARXIV_NS) or "").strip()
            title = (entry.findtext("atom:title", "", ARXIV_NS) or "").strip()
            title = " ".join(title.split())  # collapse whitespace

            # Extract PDF link
            pdf_url = ""
            for link in entry.findall("atom:link", ARXIV_NS):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break

            # Fallback: derive PDF URL from arXiv ID
            if not pdf_url and arxiv_id:
                # id looks like http://arxiv.org/abs/2301.12345v1
                aid = arxiv_id.rsplit("/abs/", 1)[-1] if "/abs/" in arxiv_id else ""
                if aid:
                    pdf_url = f"https://arxiv.org/pdf/{aid}"

            if title:
                results.append({
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "pdf_url": pdf_url,
                })

        return results

    async def fetch_full_text(self, pdf_url: str) -> str:
        """Download PDF from arXiv and extract text."""
        try:
            resp = await self._client.get(pdf_url)
            if resp.status_code != 200:
                logger.warning("arXiv PDF download failed: HTTP %d", resp.status_code)
                return ""
        except httpx.HTTPError as e:
            logger.warning("arXiv PDF download failed: %s", e)
            return ""

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
            logger.warning("Failed to parse arXiv PDF from %s", pdf_url)
            return ""

    async def close(self) -> None:
        await self._client.aclose()

    async def check_connectivity(self) -> bool:
        try:
            resp = await self._client.get(
                ARXIV_API_URL, params={"search_query": "ti:test", "max_results": 1}
            )
            return resp.status_code == 200
        except Exception:
            return False
