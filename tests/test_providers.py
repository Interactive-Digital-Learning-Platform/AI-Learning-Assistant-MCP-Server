import os

import pytest

from app.providers import get_provider
from app.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.providers.tavily import TavilyProvider


def test_parse_maps_fields_and_skips_urlless_rows():
    raw = {
        "results": [
            {"title": "A", "url": "https://a.test", "content": " hi ", "score": 0.5,
             "published_date": "2026-01-01"},
            {"title": "no url", "content": "x", "score": 0.1},
            {"url": "https://b.test", "content": "", "score": None},
        ]
    }
    out = TavilyProvider._parse(raw)

    assert [r.url for r in out] == ["https://a.test", "https://b.test"]
    assert out[0].content == "hi"
    assert out[0].published_date == "2026-01-01"
    assert out[1].title == "https://b.test"  # falls back to url
    assert out[1].score == 0.0


def test_parse_handles_missing_results_key():
    assert TavilyProvider._parse({}) == []


class _StubClient:
    def __init__(self, exc):
        self._exc = exc

    async def search(self, **kwargs):
        raise self._exc


def _provider_raising(exc, *, max_retries=0) -> TavilyProvider:
    p = TavilyProvider.__new__(TavilyProvider)
    p._client = _StubClient(exc)
    p._search_depth = "basic"
    p._timeout = 1.0
    p._max_retries = max_retries
    return p


async def test_auth_error_normalised():
    from tavily.errors import InvalidAPIKeyError

    with pytest.raises(ProviderAuthError):
        await _provider_raising(InvalidAPIKeyError("bad key")).search("q", max_results=3)


async def test_usage_limit_normalised():
    from tavily.errors import UsageLimitExceededError

    with pytest.raises(ProviderRateLimitError):
        await _provider_raising(UsageLimitExceededError("limit")).search("q", max_results=3)


async def test_timeout_normalised():
    with pytest.raises(ProviderTimeoutError):
        await _provider_raising(TimeoutError()).search("q", max_results=3)


async def test_unknown_error_normalised():
    with pytest.raises(ProviderError):
        await _provider_raising(RuntimeError("weird")).search("q", max_results=3)


def test_factory_builds_tavily(settings):
    provider = get_provider(settings)
    assert isinstance(provider, TavilyProvider)
    assert provider.name == "tavily"


def test_factory_requires_api_key(settings):
    settings.TAVILY_API_KEY = None
    with pytest.raises(ProviderAuthError):
        get_provider(settings)


def test_factory_rejects_unknown_provider(settings):
    settings.SEARCH_PROVIDER = "bing"
    with pytest.raises(ValueError):
        get_provider(settings)


@pytest.mark.integration
async def test_tavily_live_search():
    key = os.environ.get("TAVILY_API_KEY")
    if not key or key == "tvly-test-key":
        pytest.skip("real TAVILY_API_KEY not set")

    provider = TavilyProvider(api_key=key, timeout_seconds=15.0)
    results = await provider.search("what is the model context protocol", max_results=3)

    assert results
    assert all(r.url.startswith("http") for r in results)
    assert any(r.content for r in results)
