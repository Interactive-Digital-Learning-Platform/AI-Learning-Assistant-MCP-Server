import asyncio
import logging

from tavily import AsyncTavilyClient
from tavily.errors import (
    BadRequestError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    UsageLimitExceededError,
)

from app.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResult,
    ProviderTimeoutError,
)
from app.schemas import Topic

logger = logging.getLogger(__name__)


class TavilyProvider:
    """Tavily Search API implementation of ``WebSearchProvider``.

    Tavily returns pre-extracted, ranked snippets (``content`` + ``score``) in a
    single call, so mapping to :class:`ProviderResult` is near 1:1.
    """

    name = "tavily"

    def __init__(
        self,
        api_key: str,
        *,
        search_depth: str = "basic",
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        self._client = AsyncTavilyClient(api_key=api_key)
        self._search_depth = search_depth
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    async def search(
        self,
        query: str,
        *,
        max_results: int,
        topic: Topic = "general",
    ) -> list[ProviderResult]:
        attempt = 0
        while True:
            try:
                raw = await self._client.search(
                    query=query,
                    search_depth=self._search_depth,
                    topic=topic,
                    max_results=max_results,
                    include_answer=False,
                    include_raw_content=False,
                    timeout=self._timeout,
                )
                return self._parse(raw)

            except (MissingAPIKeyError, InvalidAPIKeyError) as exc:
                raise ProviderAuthError(str(exc)) from exc

            except UsageLimitExceededError as exc:
                # Retryable: back off and try again within the budget.
                if attempt >= self._max_retries:
                    raise ProviderRateLimitError(str(exc)) from exc
                await self._backoff(attempt)

            except BadRequestError as exc:
                raise ProviderError(f"tavily rejected the request: {exc}") from exc

            except TimeoutError as exc:
                if attempt >= self._max_retries:
                    raise ProviderTimeoutError("tavily search timed out") from exc
                await self._backoff(attempt)

            except Exception as exc:
                if attempt >= self._max_retries:
                    raise ProviderError(f"tavily search failed: {exc}") from exc
                logger.warning(
                    "tavily search error; retrying",
                    extra={"attempt": attempt, "error": str(exc)},
                )
                await self._backoff(attempt)

            attempt += 1

    @staticmethod
    async def _backoff(attempt: int) -> None:
        await asyncio.sleep(min(2**attempt, 8) * 0.5)

    @staticmethod
    def _parse(raw: dict) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        for item in raw.get("results", []) or []:
            url = item.get("url")
            if not url:
                continue
            results.append(
                ProviderResult(
                    title=item.get("title") or url,
                    url=url,
                    content=(item.get("content") or "").strip(),
                    score=float(item.get("score") or 0.0),
                    published_date=item.get("published_date"),
                )
            )
        return results
