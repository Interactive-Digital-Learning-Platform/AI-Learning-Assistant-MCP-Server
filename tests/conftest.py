import os

os.environ.setdefault("MCP_AUTH_TOKEN", "test-shared-secret")
os.environ.setdefault("TAVILY_API_KEY", "tvly-test-key")
os.environ.setdefault("LOG_JSON", "false")

import pytest

from app.config import Settings
from app.providers.base import ProviderResult


class FakeProvider:
    name = "fake"

    def __init__(self, results=None, error: Exception | None = None):
        self._results = results if results is not None else []
        self._error = error
        self.calls: list[dict] = []

    async def search(self, query, *, max_results, topic="general"):
        self.calls.append({"query": query, "max_results": max_results, "topic": topic})
        if self._error is not None:
            raise self._error
        return list(self._results)


@pytest.fixture
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@pytest.fixture
def sample_results() -> list[ProviderResult]:
    return [
        ProviderResult(
            title="Python 3.13 released",
            url="https://example.com/py313",
            content="Python 3.13 brings a JIT and free-threaded builds.",
            score=0.91,
            published_date="2026-08-01",
        ),
        ProviderResult(
            title="Release notes",
            url="https://example.com/notes",
            content="Detailed changelog.",
            score=0.72,
        ),
    ]
