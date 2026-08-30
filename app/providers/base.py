from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.schemas import Topic


@dataclass(slots=True)
class ProviderResult:
    """Provider-agnostic single search result."""

    title: str
    url: str
    content: str
    score: float
    published_date: str | None = None


class ProviderError(Exception):
    """Base class for web-search provider failures."""


class ProviderAuthError(ProviderError):
    """Invalid or missing provider credentials."""


class ProviderRateLimitError(ProviderError):
    """Provider quota or rate limit exceeded."""


class ProviderTimeoutError(ProviderError):
    """Provider did not respond within the allotted time."""


@runtime_checkable
class WebSearchProvider(Protocol):
    """Interface every web-search backend must implement.

    Implementations own provider-specific auth, HTTP, retries and payload
    parsing. They must translate transport/HTTP failures into the
    ``ProviderError`` hierarchy above; anything else is treated as an
    unexpected internal error by the tool layer.
    """

    name: str

    async def search(
        self,
        query: str,
        *,
        max_results: int,
        topic: Topic = "general",
    ) -> list[ProviderResult]: ...
