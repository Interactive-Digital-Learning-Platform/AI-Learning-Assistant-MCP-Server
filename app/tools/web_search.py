import asyncio
import hashlib
import logging
import time

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token

from app.config import Settings
from app.providers import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    WebSearchProvider,
)
from app.rate_limit import TokenBucket
from app.schemas import Topic, WebSearchInput, WebSearchResponse, WebSearchResultItem

logger = logging.getLogger(__name__)


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]


def _caller_key() -> str:
    try:
        token = get_access_token()
    except Exception:  # noqa: BLE001 - not in an HTTP context (e.g. stdio/tests)
        return "default"
    return token.client_id if token else "default"


def register_web_search(
    mcp: FastMCP,
    provider: WebSearchProvider,
    settings: Settings,
) -> None:
    """Register the ``web_search`` tool on the given FastMCP server.

    Kept provider-agnostic: everything below talks to the ``WebSearchProvider``
    interface only. Adding another tool later follows the same
    ``register_*(mcp, deps)`` shape.
    """

    limiter = TokenBucket(settings.WEB_SEARCH_RATE_LIMIT_PER_MIN)
    default_max = settings.WEB_SEARCH_DEFAULT_MAX_RESULTS
    hard_limit = settings.WEB_SEARCH_MAX_RESULTS_LIMIT
    overall_timeout = settings.WEB_SEARCH_TIMEOUT_SECONDS

    @mcp.tool(
        name="web_search",
        description=(
            "Search the public web for current or external information and return "
            "ranked results with title, URL and a relevant content snippet. Use "
            "for recent events, news, live data or facts outside the local "
            "knowledge base."
        ),
    )
    async def web_search(
        query: str,
        max_results: int | None = None,
        topic: Topic = "general",
    ) -> WebSearchResponse:
        params = WebSearchInput(query=query, max_results=max_results, topic=topic)

        cleaned = params.query.strip()
        if not cleaned:
            raise ToolError("query must not be empty")

        effective_max = min(params.max_results or default_max, hard_limit)
        caller = _caller_key()

        if not limiter.allow(caller):
            logger.warning(
                "web_search rate limited",
                extra={"tool": "web_search", "caller": caller},
            )
            raise ToolError("web search rate limit exceeded; retry shortly")

        started = time.monotonic()
        try:
            provider_results = await asyncio.wait_for(
                provider.search(cleaned, max_results=effective_max, topic=params.topic),
                timeout=overall_timeout,
            )
        except (TimeoutError, ProviderTimeoutError) as exc:
            logger.warning(
                "web_search timed out",
                extra={"tool": "web_search", "query_hash": _query_hash(cleaned)},
            )
            raise ToolError("web search timed out") from exc
        except ProviderAuthError as exc:
            logger.error("web_search provider auth failure", exc_info=exc)
            raise ToolError("web search provider is misconfigured") from exc
        except ProviderRateLimitError as exc:
            logger.warning("web_search provider rate limited", extra={"tool": "web_search"})
            raise ToolError("web search provider quota exceeded; retry later") from exc
        except ProviderError as exc:
            logger.error("web_search provider failure", exc_info=exc)
            raise ToolError("web search provider unavailable") from exc

        items = [
            WebSearchResultItem(
                title=r.title,
                url=r.url,
                content=r.content,
                score=r.score,
                published_date=r.published_date,
            )
            for r in provider_results
        ]

        logger.info(
            "web_search completed",
            extra={
                "tool": "web_search",
                "provider": provider.name,
                "query_hash": _query_hash(cleaned),
                "result_count": len(items),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "status": "ok",
            },
        )

        return WebSearchResponse(
            query=cleaned,
            provider=provider.name,
            result_count=len(items),
            results=items,
        )
