"""CrossRef API client."""

from typing import Any

from ref_validator.apis.base import BaseAcademicAPI


class CrossRefAPI(BaseAcademicAPI):
    API_NAME = "crossref"
    BASE_URL = "https://api.crossref.org"

    def __init__(self, *, mailto: str = "", **kwargs: Any):
        headers = {}
        if mailto:
            headers["User-Agent"] = f"ref-validator/0.1.0 (mailto:{mailto})"
        super().__init__(headers=headers, **kwargs)

    async def search_by_title(self, title: str, rows: int = 5) -> list[dict[str, Any]]:
        """Search for works by title."""
        params = {"query.title": title, "rows": rows, "select": "DOI,title,author,published-print,container-title,volume,page"}
        data = await self._request("GET", "/works", params=params)
        return data.get("message", {}).get("items", [])

    async def get_by_doi(self, doi: str) -> dict[str, Any]:
        """Look up a work by DOI."""
        data = await self._request("GET", f"/works/{doi}")
        return data.get("message", {})

    async def check_connectivity(self) -> bool:
        try:
            await self._request("GET", "/works", params={"rows": 1})
            return True
        except Exception:
            return False
