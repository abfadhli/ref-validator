"""OpenAlex API client."""

from typing import Any

from ref_validator.apis.base import BaseAcademicAPI


class OpenAlexAPI(BaseAcademicAPI):
    API_NAME = "openalex"
    BASE_URL = "https://api.openalex.org"

    def __init__(self, *, mailto: str = "", **kwargs: Any):
        headers = {}
        if mailto:
            headers["User-Agent"] = f"ref-validator/0.1.0 (mailto:{mailto})"
        super().__init__(headers=headers, **kwargs)
        self._mailto = mailto

    async def search_by_title(self, title: str, per_page: int = 5) -> list[dict[str, Any]]:
        """Search for works by title."""
        params: dict[str, Any] = {
            "search": title,
            "per_page": per_page,
        }
        if self._mailto:
            params["mailto"] = self._mailto
        data = await self._request("GET", "/works", params=params)
        return data.get("results", [])

    async def get_by_doi(self, doi: str) -> dict[str, Any]:
        """Look up a work by DOI."""
        params: dict[str, Any] = {}
        if self._mailto:
            params["mailto"] = self._mailto
        # OpenAlex uses the full DOI URL as identifier
        doi_url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
        return await self._request("GET", f"/works/{doi_url}", params=params)

    async def check_connectivity(self) -> bool:
        try:
            await self._request("GET", "/works", params={"per_page": 1})
            return True
        except Exception:
            return False
