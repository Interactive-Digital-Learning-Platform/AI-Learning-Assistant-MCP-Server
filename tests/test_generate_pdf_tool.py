from datetime import datetime

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from app.renderers.base import RendererError
from app.tools import register_generate_pdf
from tests.conftest import FakeObjectStore, FakeRenderer


def _server(renderer, store, settings) -> FastMCP:
    mcp = FastMCP("test")
    register_generate_pdf(mcp, renderer, store, settings)
    return mcp


async def _call(mcp: FastMCP, **args):
    async with Client(mcp) as client:
        return await client.call_tool("generate_pdf", args)


async def test_tool_is_discoverable(pdf_settings):
    async with Client(_server(FakeRenderer(), FakeObjectStore(), pdf_settings)) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "generate_pdf" in tools


async def test_returns_completed_response(pdf_settings, sample_markdown):
    renderer = FakeRenderer(page_count=3)
    store = FakeObjectStore()

    result = await _call(
        _server(renderer, store, pdf_settings),
        title="Photosynthesis Explained",
        markdown_body=sample_markdown,
    )
    data = result.data

    assert data.status == "completed"
    assert data.page_count == 3
    assert data.mime_type == "application/pdf"
    assert data.filename == "Photosynthesis Explained.pdf"
    assert data.document_id
    assert data.download_url and "X-Amz-Signature" in data.download_url
    assert "response-content-disposition" in data.download_url
    datetime.fromisoformat(data.expires_at)
    assert store.puts[0]["key"] == f"{data.document_id}/photosynthesis-explained.pdf"
    assert renderer.calls[0]["title"] == "Photosynthesis Explained"


async def test_blank_title_rejected(pdf_settings, sample_markdown):
    with pytest.raises(ToolError):
        await _call(
            _server(FakeRenderer(), FakeObjectStore(), pdf_settings),
            title="   ",
            markdown_body=sample_markdown,
        )


async def test_blank_body_rejected(pdf_settings):
    with pytest.raises(ToolError):
        await _call(
            _server(FakeRenderer(), FakeObjectStore(), pdf_settings),
            title="Newton's Laws",
            markdown_body="   ",
        )


async def test_empty_body_rejected_by_schema(pdf_settings):
    with pytest.raises(ToolError):
        await _call(
            _server(FakeRenderer(), FakeObjectStore(), pdf_settings),
            title="Newton's Laws",
            markdown_body="",
        )


async def test_body_over_cap_rejected(pdf_settings):
    pdf_settings.PDF_MARKDOWN_MAX_CHARS = 32
    with pytest.raises(ToolError, match="too large"):
        await _call(
            _server(FakeRenderer(), FakeObjectStore(), pdf_settings),
            title="Long",
            markdown_body="word " * 50,
        )


async def test_renderer_failure_returns_failed(pdf_settings, sample_markdown):
    store = FakeObjectStore()
    result = await _call(
        _server(FakeRenderer(error=RendererError("boom")), store, pdf_settings),
        title="Photosynthesis",
        markdown_body=sample_markdown,
    )

    assert result.data.status == "failed"
    assert result.data.download_url is None
    assert result.data.error == "rendering failed"
    assert not store.puts


async def test_render_timeout_returns_failed(pdf_settings, sample_markdown):
    pdf_settings.PDF_RENDER_TIMEOUT_SECONDS = 0.05
    result = await _call(
        _server(FakeRenderer(delay=1.0), FakeObjectStore(), pdf_settings),
        title="Photosynthesis",
        markdown_body=sample_markdown,
    )

    assert result.data.status == "failed"
    assert result.data.error == "rendering failed"


async def test_upload_failure_returns_failed(pdf_settings, sample_markdown):
    store = FakeObjectStore(put_error=RuntimeError("s3 down"))
    result = await _call(
        _server(FakeRenderer(), store, pdf_settings),
        title="Photosynthesis",
        markdown_body=sample_markdown,
    )

    assert result.data.status == "failed"
    assert result.data.error == "storage upload failed"
    assert result.data.download_url is None


async def test_page_limit_returns_failed(pdf_settings, sample_markdown):
    pdf_settings.PDF_MAX_PAGE_COUNT = 2
    store = FakeObjectStore()
    result = await _call(
        _server(FakeRenderer(page_count=5), store, pdf_settings),
        title="Photosynthesis",
        markdown_body=sample_markdown,
    )

    assert result.data.status == "failed"
    assert result.data.error == "document too long"
    assert result.data.page_count == 5
    assert not store.puts


async def test_rate_limit_exceeded(pdf_settings, sample_markdown):
    pdf_settings.PDF_GENERATION_RATE_LIMIT_PER_MIN = 1
    mcp = _server(FakeRenderer(), FakeObjectStore(), pdf_settings)

    await _call(mcp, title="First", markdown_body=sample_markdown)
    with pytest.raises(ToolError, match="rate limit"):
        await _call(mcp, title="Second", markdown_body=sample_markdown)


async def test_presigned_url_uses_public_endpoint(pdf_settings, sample_markdown):
    store = FakeObjectStore(public_endpoint="http://storage.example:8080")
    result = await _call(
        _server(FakeRenderer(), store, pdf_settings),
        title="Newton Laws",
        markdown_body=sample_markdown,
    )

    assert result.data.download_url.startswith(
        "http://storage.example:8080/learning-documents/"
    )


async def test_filename_override_is_sanitised(pdf_settings, sample_markdown):
    store = FakeObjectStore()
    result = await _call(
        _server(FakeRenderer(), store, pdf_settings),
        title="Anything",
        markdown_body=sample_markdown,
        filename="../secret/My Notes",
    )

    assert result.data.filename == "My Notes.pdf"
    assert store.puts[0]["key"] == f"{result.data.document_id}/my-notes.pdf"
