"""Unpaywall API client for finding open access PDFs."""

from typing import Any

from ref_validator.apis.base import BaseAcademicAPI


class UnpaywallAPI(BaseAcademicAPI):
    API_NAME = "unpaywall"
    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(self, *, email: str, **kwargs: Any):
        super().__init__(**kwargs)
        self._email = email

    async def get_oa_pdf_url(self, doi: str) -> str | None:
        """Find an open access PDF URL for a DOI. Returns None if not found."""
        try:
            data = await self._request(
                "GET",
                f"/{doi}",
                params={"email": self._email},
            )
        except Exception:
            return None

        best = data.get("best_oa_location")
        if best:
            return best.get("url_for_pdf") or best.get("url")
        return None

    async def check_connectivity(self) -> bool:
        try:
            # Use a known DOI to test
            await self._request(
                "GET",
                "/10.1038/nature12373",
                params={"email": self._email},
            )
            return True
        except Exception:
            return False
