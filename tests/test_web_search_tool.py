import asyncio

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from app.providers.base import ProviderError, ProviderTimeoutError
from app.tools import register_web_search
from tests.conftest import FakeProvider


def _server(provider, settings) -> FastMCP:
    mcp = FastMCP("test")
    register_web_search(mcp, provider, settings)
    return mcp


async def _call(mcp: FastMCP, **args):
    async with Client(mcp) as client:
        return await client.call_tool("web_search", args)


async def test_returns_normalised_response(settings, sample_results):
    provider = FakeProvider(results=sample_results)
    result = await _call(_server(provider, settings), query="python 3.13")

    assert result.data.provider == "fake"
    assert result.data.result_count == 2
    first = result.data.results[0]
    assert first.title == "Python 3.13 released"
    assert first.url == "https://example.com/py313"
    assert first.content
    assert first.published_date == "2026-08-01"


async def test_tool_is_discoverable(settings):
    async with Client(_server(FakeProvider(), settings)) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "web_search" in tools


async def test_blank_query_rejected(settings):
    with pytest.raises(ToolError):
        await _call(_server(FakeProvider(), settings), query="   ")


async def test_empty_query_rejected_by_schema(settings):
    with pytest.raises(ToolError):
        await _call(_server(FakeProvider(), settings), query="")


async def test_max_results_clamped_to_limit(settings, sample_results):
    settings.WEB_SEARCH_MAX_RESULTS_LIMIT = 3
    provider = FakeProvider(results=sample_results)

    await _call(_server(provider, settings), query="q", max_results=50)

    assert provider.calls[0]["max_results"] == 3


async def test_default_max_results_applied(settings, sample_results):
    settings.WEB_SEARCH_DEFAULT_MAX_RESULTS = 4
    provider = FakeProvider(results=sample_results)

    await _call(_server(provider, settings), query="q")

    assert provider.calls[0]["max_results"] == 4


async def test_provider_empty_is_not_an_error(settings):
    result = await _call(_server(FakeProvider(results=[]), settings), query="obscure")
    assert result.data.result_count == 0
    assert result.data.results == []


async def test_provider_error_becomes_tool_error(settings):
    provider = FakeProvider(error=ProviderError("boom"))
    with pytest.raises(ToolError, match="unavailable"):
        await _call(_server(provider, settings), query="q")


async def test_provider_timeout_becomes_tool_error(settings):
    provider = FakeProvider(error=ProviderTimeoutError("slow"))
    with pytest.raises(ToolError, match="timed out"):
        await _call(_server(provider, settings), query="q")


async def test_overall_timeout_enforced(settings):
    class SlowProvider(FakeProvider):
        async def search(self, query, *, max_results, topic="general"):
            await asyncio.sleep(1)
            return []

    settings.WEB_SEARCH_TIMEOUT_SECONDS = 0.05
    with pytest.raises(ToolError, match="timed out"):
        await _call(_server(SlowProvider(), settings), query="q")


async def test_rate_limit_exceeded(settings, sample_results):
    settings.WEB_SEARCH_RATE_LIMIT_PER_MIN = 1
    provider = FakeProvider(results=sample_results)
    mcp = _server(provider, settings)

    await _call(mcp, query="first")
    with pytest.raises(ToolError, match="rate limit"):
        await _call(mcp, query="second")
