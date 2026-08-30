from app.config import Settings
from app.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResult,
    ProviderTimeoutError,
    WebSearchProvider,
)

__all__ = [
    "ProviderAuthError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderResult",
    "ProviderTimeoutError",
    "WebSearchProvider",
    "get_provider",
]


def get_provider(settings: Settings) -> WebSearchProvider:
    """Build the configured web-search provider.

    Add a new backend by implementing :class:`WebSearchProvider` and wiring a
    branch here keyed on ``SEARCH_PROVIDER``.
    """
    name = settings.SEARCH_PROVIDER.lower()

    if name == "tavily":
        from app.providers.tavily import TavilyProvider

        if settings.TAVILY_API_KEY is None:
            raise ProviderAuthError("TAVILY_API_KEY is not configured")

        return TavilyProvider(
            api_key=settings.TAVILY_API_KEY.get_secret_value(),
            search_depth=settings.TAVILY_SEARCH_DEPTH,
            timeout_seconds=settings.WEB_SEARCH_TIMEOUT_SECONDS,
            max_retries=settings.WEB_SEARCH_PROVIDER_MAX_RETRIES,
        )

    raise ValueError(f"Unknown SEARCH_PROVIDER: {settings.SEARCH_PROVIDER!r}")
