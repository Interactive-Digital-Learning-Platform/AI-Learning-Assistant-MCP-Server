import logging

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth import StaticBearerVerifier
from app.config import settings
from app.logging_config import configure_logging
from app.providers import get_provider
from app.tools import register_web_search

configure_logging(level=settings.LOG_LEVEL, json_output=settings.LOG_JSON)
logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP(
    "AI-Learning-Assistant-MCP-Server",
    instructions=(
        "Capability server for the AI Learning Assistant. Provides a `web_search` "
        "tool that returns ranked public-web results with content snippets."
    ),
    auth=StaticBearerVerifier(settings.MCP_AUTH_TOKEN.get_secret_value()),
)

_provider = get_provider(settings)
register_web_search(mcp, _provider, settings)

logger.info(
    "MCP server initialised",
    extra={"provider": _provider.name, "tools": ["web_search"]},
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
