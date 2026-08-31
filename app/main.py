import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth import StaticBearerVerifier
from app.config import settings
from app.logging_config import configure_logging
from app.providers import get_provider
from app.renderers import get_renderer
from app.storage import get_object_store
from app.tools import register_generate_pdf, register_web_search

configure_logging(level=settings.LOG_LEVEL, json_output=settings.LOG_JSON)
logger = logging.getLogger(__name__)

_provider = get_provider(settings)
_renderer = get_renderer(settings) if settings.PDF_GENERATION_ENABLED else None
_object_store = get_object_store(settings) if settings.PDF_GENERATION_ENABLED else None
_pdf_enabled = _renderer is not None and _object_store is not None

_tools = ["web_search"]
_instructions = (
    "Capability server for the AI Learning Assistant. Provides a `web_search` "
    "tool that returns ranked public-web results with content snippets"
)
if _pdf_enabled:
    _tools.append("generate_pdf")
    _instructions += (
        ", and a `generate_pdf` tool that renders caller-supplied markdown into a "
        "downloadable PDF stored in object storage and returns a presigned URL"
    )
_instructions += "."


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[dict]:
    if _object_store is not None:
        await _object_store.open()
        if settings.S3_ENSURE_BUCKET:
            await _object_store.ensure_bucket()
    try:
        yield {}
    finally:
        if _object_store is not None:
            await _object_store.close()


mcp: FastMCP = FastMCP(
    "AI-Learning-Assistant-MCP-Server",
    instructions=_instructions,
    auth=StaticBearerVerifier(settings.MCP_AUTH_TOKEN.get_secret_value()),
    lifespan=_lifespan,
)

register_web_search(mcp, _provider, settings)
if _pdf_enabled:
    register_generate_pdf(mcp, _renderer, _object_store, settings)

logger.info(
    "MCP server initialised",
    extra={"provider": _provider.name, "tools": _tools},
)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "provider": _provider.name})


def run() -> None:
    mcp.run(
        transport="http",
        host=settings.HOST,
        port=settings.PORT,
        show_banner=False,
    )


if __name__ == "__main__":
    run()
