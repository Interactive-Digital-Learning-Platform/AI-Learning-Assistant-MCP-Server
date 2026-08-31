import asyncio
import os

os.environ.setdefault("MCP_AUTH_TOKEN", "test-shared-secret")
os.environ.setdefault("TAVILY_API_KEY", "tvly-test-key")
os.environ.setdefault("LOG_JSON", "false")

import pytest

from app.config import Settings
from app.providers.base import ProviderResult
from app.renderers.base import RenderResult
from app.storage.object_store import ObjectStore


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


class FakeRenderer:
    name = "fake"

    def __init__(
        self,
        *,
        page_count: int = 2,
        pdf_bytes: bytes = b"%PDF-1.4 fake document\n%%EOF",
        error: Exception | None = None,
        delay: float = 0.0,
    ):
        self._page_count = page_count
        self._pdf_bytes = pdf_bytes
        self._error = error
        self._delay = delay
        self.calls: list[dict] = []

    async def render(self, *, title: str, markdown_body: str) -> RenderResult:
        self.calls.append({"title": title, "markdown_body": markdown_body})
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return RenderResult(pdf_bytes=self._pdf_bytes, page_count=self._page_count)


class FakeObjectStore:
    def __init__(
        self,
        *,
        public_endpoint: str = "http://storage.example:8080",
        bucket: str = "learning-documents",
        put_error: Exception | None = None,
    ):
        self.bucket = bucket
        self._public_endpoint = public_endpoint.rstrip("/")
        self._put_error = put_error
        self.puts: list[dict] = []

    @staticmethod
    def make_object_key(document_id: str, filename: str) -> str:
        return ObjectStore.make_object_key(document_id, filename)

    async def put_pdf(self, key: str, data: bytes) -> None:
        if self._put_error is not None:
            raise self._put_error
        self.puts.append({"key": key, "size": len(data)})

    async def presigned_get_url(self, key: str, *, filename: str, expires_in: int) -> str:
        from urllib.parse import quote

        disposition = quote(f'attachment; filename="{filename}"')
        return (
            f"{self._public_endpoint}/{self.bucket}/{key}"
            f"?X-Amz-Algorithm=AWS4-HMAC-SHA256"
            f"&X-Amz-Expires={expires_in}"
            f"&X-Amz-Signature=deadbeefcafe"
            f"&response-content-disposition={disposition}"
        )


@pytest.fixture
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@pytest.fixture
def pdf_settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        PDF_GENERATION_ENABLED=True,
        PDF_RENDERER="weasyprint",
        S3_ENDPOINT_URL="http://minio.internal:9000",
        S3_PUBLIC_ENDPOINT_URL="http://storage.example:8080",
        S3_ACCESS_KEY="test-access-key",
        S3_SECRET_KEY="test-secret-key",
        S3_BUCKET="learning-documents",
    )


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


@pytest.fixture
def sample_markdown() -> str:
    return (
        "# Photosynthesis\n\n"
        "## Overview\n\n"
        "Photosynthesis converts light energy into chemical energy stored as glucose.\n\n"
        "- Light-dependent reactions\n"
        "- The Calvin cycle\n\n"
        "## Summary\n\n"
        "Plants, algae and some bacteria use photosynthesis to build sugars from "
        "carbon dioxide and water.\n"
    )
