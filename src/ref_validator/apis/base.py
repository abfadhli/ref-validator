"""Base academic API client with rate limiting and retries."""

import asyncio
import logging
from typing import Any

import httpx

from ref_validator.errors import APIError

logger = logging.getLogger(__name__)


class BaseAcademicAPI:
    """Base class for academic API clients with rate limiting and retry logic."""

    API_NAME: str = "base"
    BASE_URL: str = ""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        max_concurrent: int = 5,
        headers: dict[str, str] | None = None,
    ):
        self._timeout = timeout
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout,
            headers=headers or {},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with rate limiting and retries."""
        async with self._semaphore:
            last_error: Exception | None = None
            for attempt in range(self._max_retries):
                try:
                    response = await self._client.request(
                        method, path, params=params, json=json
                    )
                    if response.status_code == 429:
                        retry_after = float(response.headers.get("retry-after", 2))
                        logger.warning(
                            "%s: rate limited, retrying in %.1fs", self.API_NAME, retry_after
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    if response.status_code >= 500:
                        logger.warning(
                            "%s: server error %d, attempt %d/%d",
                            self.API_NAME, response.status_code, attempt + 1, self._max_retries,
                        )
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    raise APIError(
                        f"{self.API_NAME}: HTTP {e.response.status_code}",
                        api_name=self.API_NAME,
                        status_code=e.response.status_code,
                    ) from e
                except httpx.HTTPError as e:
                    last_error = e
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(2 ** attempt)

            raise APIError(
                f"{self.API_NAME}: request failed after {self._max_retries} attempts: {last_error}",
                api_name=self.API_NAME,
            )

    async def close(self) -> None:
        await self._client.aclose()

    async def check_connectivity(self) -> bool:
        """Check if the API is reachable. Override in subclasses."""
        raise NotImplementedError
