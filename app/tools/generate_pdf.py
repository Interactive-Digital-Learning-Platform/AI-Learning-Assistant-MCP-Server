import asyncio
import hashlib
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token

from app.config import Settings
from app.rate_limit import TokenBucket
from app.renderers import DocumentRenderer, RendererError
from app.schemas import GeneratePdfInput, GeneratePdfResponse
from app.storage import ObjectStore

logger = logging.getLogger(__name__)


def _caller_key() -> str:
    try:
        token = get_access_token()
    except Exception:  # noqa: BLE001 - not in an HTTP context (e.g. stdio/tests)
        return "default"
    return token.client_id if token else "default"


def _body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def _pretty_filename(raw: str) -> str:
    name = Path(raw.strip()).name.strip()
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    name = name.strip(" .") or "document"
    return f"{name[:180]}.pdf"


def register_generate_pdf(
    mcp: FastMCP,
    renderer: DocumentRenderer,
    store: ObjectStore,
    settings: Settings,
) -> None:
    """Register the ``generate_pdf`` tool on the given FastMCP server.

    The tool owns rendering, storage upload, presigned-URL minting, validation
    and rate limiting. It never calls an LLM and never authors content.
    """

    limiter = TokenBucket(settings.PDF_GENERATION_RATE_LIMIT_PER_MIN)
    markdown_max = settings.PDF_MARKDOWN_MAX_CHARS
    max_pages = settings.PDF_MAX_PAGE_COUNT
    render_timeout = settings.PDF_RENDER_TIMEOUT_SECONDS
    upload_timeout = settings.PDF_UPLOAD_TIMEOUT_SECONDS
    url_ttl = settings.PDF_URL_EXPIRES_SECONDS

    @mcp.tool(
        name="generate_pdf",
        description=(
            "Render a study document from caller-supplied structured markdown "
            "into a PDF, store it in object storage, and return a presigned "
            "download URL plus metadata. This tool does NOT call an LLM and does "
            "NOT author content - the caller supplies the finished markdown."
        ),
    )
    async def generate_pdf(
        title: str,
        markdown_body: str,
        filename: str | None = None,
    ) -> GeneratePdfResponse:
        params = GeneratePdfInput(
            title=title, markdown_body=markdown_body, filename=filename
        )

        title_clean = params.title.strip()
        body_clean = params.markdown_body.strip()
        if not title_clean or not body_clean:
            raise ToolError("title and markdown_body must not be empty")
        if len(body_clean) > markdown_max:
            raise ToolError("markdown_body too large")

        caller = _caller_key()
        if not limiter.allow(caller):
            logger.warning(
                "generate_pdf rate limited",
                extra={"tool": "generate_pdf", "caller": caller},
            )
            raise ToolError("pdf generation rate limit exceeded; retry shortly")

        document_id = uuid4().hex
        pretty = _pretty_filename(params.filename or title_clean)
        started = time.monotonic()

        try:
            result = await asyncio.wait_for(
                renderer.render(title=title_clean, markdown_body=body_clean),
                timeout=render_timeout,
            )
        except (TimeoutError, RendererError) as exc:
            logger.error(
                "generate_pdf render failed",
                exc_info=exc,
                extra={"tool": "generate_pdf", "document_id": document_id},
            )
            return GeneratePdfResponse(
                status="failed",
                document_id=document_id,
                filename=pretty,
                error="rendering failed",
            )

        if result.page_count > max_pages:
            logger.warning(
                "generate_pdf exceeded page limit",
                extra={
                    "tool": "generate_pdf",
                    "document_id": document_id,
                    "page_count": result.page_count,
                },
            )
            return GeneratePdfResponse(
                status="failed",
                document_id=document_id,
                filename=pretty,
                page_count=result.page_count,
                error="document too long",
            )

        key = store.make_object_key(document_id, pretty)
        try:
            await asyncio.wait_for(
                store.put_pdf(key, result.pdf_bytes),
                timeout=upload_timeout,
            )
        except Exception as exc:
            logger.error(
                "generate_pdf upload failed",
                exc_info=exc,
                extra={"tool": "generate_pdf", "document_id": document_id},
            )
            return GeneratePdfResponse(
                status="failed",
                document_id=document_id,
                filename=pretty,
                page_count=result.page_count,
                error="storage upload failed",
            )

        download_url = await store.presigned_get_url(
            key, filename=pretty, expires_in=url_ttl
        )
        expires_at = (datetime.now(UTC) + timedelta(seconds=url_ttl)).isoformat()

        logger.info(
            "generate_pdf completed",
            extra={
                "tool": "generate_pdf",
                "document_id": document_id,
                "page_count": result.page_count,
                "bytes": len(result.pdf_bytes),
                "body_hash": _body_hash(body_clean),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "status": "ok",
            },
        )

        return GeneratePdfResponse(
            status="completed",
            document_id=document_id,
            filename=pretty,
            mime_type="application/pdf",
            page_count=result.page_count,
            download_url=download_url,
            expires_at=expires_at,
        )
