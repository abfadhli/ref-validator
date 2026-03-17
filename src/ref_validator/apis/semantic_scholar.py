"""Semantic Scholar API client."""

from typing import Any

from ref_validator.apis.base import BaseAcademicAPI


class SemanticScholarAPI(BaseAcademicAPI):
    API_NAME = "semantic_scholar"
    BASE_URL = "https://api.semanticscholar.org"

    def __init__(self, *, api_key: str = "", **kwargs: Any):
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        super().__init__(headers=headers, **kwargs)

    async def search_by_title(self, title: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search for papers by title."""
        params = {
            "query": title,
            "limit": limit,
            "fields": "title,authors,year,venue,externalIds,abstract",
        }
        data = await self._request("GET", "/graph/v1/paper/search", params=params)
        return data.get("data", [])

    async def get_by_doi(self, doi: str) -> dict[str, Any]:
        """Look up a paper by DOI."""
        return await self._request(
            "GET",
            f"/graph/v1/paper/DOI:{doi}",
            params={"fields": "title,authors,year,venue,externalIds,abstract"},
        )

    async def get_abstract(self, paper_id: str) -> str:
        """Get the abstract for a paper by its Semantic Scholar ID."""
        data = await self._request(
            "GET",
            f"/graph/v1/paper/{paper_id}",
            params={"fields": "abstract"},
        )
        return data.get("abstract", "") or ""

    async def check_connectivity(self) -> bool:
        try:
            await self._request("GET", "/graph/v1/paper/search", params={"query": "test", "limit": 1})
            return True
        except Exception:
            return False
