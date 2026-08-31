import asyncio
import base64
import logging
from html import escape
from urllib.parse import unquote_to_bytes

from app.renderers.base import RendererError, RenderResult

logger = logging.getLogger(__name__)

_MARKDOWN_EXTENSIONS = ["extra", "sane_lists"]

_CSS = """
@page { size: A4; margin: 2cm; }
* { box-sizing: border-box; }
body {
  font-family: "DejaVu Sans", "Helvetica", "Arial", sans-serif;
  font-size: 11pt; line-height: 1.5; color: #1a1a1a;
}
h1 { font-size: 20pt; margin: 0 0 0.6em; }
h2 {
  font-size: 15pt; margin: 1.2em 0 0.4em;
  border-bottom: 1px solid #d0d0d0; padding-bottom: 0.15em;
}
h3 { font-size: 12.5pt; margin: 1em 0 0.3em; }
p { margin: 0 0 0.7em; }
ul, ol { margin: 0 0 0.7em 1.4em; padding: 0; }
li { margin: 0.2em 0; }
code {
  font-family: "DejaVu Sans Mono", monospace; font-size: 9.5pt;
  background: #f2f2f2; padding: 0.1em 0.3em; border-radius: 3px;
}
pre {
  background: #f6f6f6; border: 1px solid #e0e0e0; border-radius: 4px;
  padding: 0.8em; white-space: pre-wrap; overflow-wrap: break-word; font-size: 9.5pt;
}
pre code { background: none; padding: 0; }
blockquote {
  margin: 0 0 0.7em; padding: 0.2em 0 0.2em 1em;
  border-left: 3px solid #c0c0c0; color: #444;
}
table { border-collapse: collapse; width: 100%; margin: 0 0 0.9em; font-size: 10pt; }
th, td { border: 1px solid #cfcfcf; padding: 0.4em 0.6em; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
img { max-width: 100%; }
a { color: #1a1a1a; text-decoration: underline; }
"""


def _blocked_url_fetcher(url, *_args, **_kwargs):
    if not url.startswith("data:"):
        raise RendererError(f"refusing to fetch external resource: {url!r}")

    header, _, payload = url[len("data:") :].partition(",")
    mime_type = header.split(";", 1)[0] or "text/plain"
    if header.rstrip().endswith(";base64"):
        data = base64.b64decode(payload)
    else:
        data = unquote_to_bytes(payload)
    return {"string": data, "mime_type": mime_type}


def _build_html(title: str, body_html: str) -> str:
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>'
        + escape(title, quote=True)
        + "</title><style>"
        + _CSS
        + "</style></head><body><main>"
        + body_html
        + "</main></body></html>"
    )


class WeasyPrintRenderer:
    """Markdown -> HTML/CSS -> PDF via WeasyPrint."""

    name = "weasyprint"

    async def render(self, *, title: str, markdown_body: str) -> RenderResult:
        return await asyncio.to_thread(self._render, title, markdown_body)

    def _render(self, title: str, markdown_body: str) -> RenderResult:
        try:
            import markdown as markdown_lib
            import weasyprint
        except ImportError as exc:
            raise RendererError(f"weasyprint renderer unavailable: {exc}") from exc

        body_html = markdown_lib.markdown(
            markdown_body,
            extensions=_MARKDOWN_EXTENSIONS,
            output_format="html5",
        )
        document_html = _build_html(title, body_html)

        try:
            rendered = weasyprint.HTML(
                string=document_html,
                url_fetcher=_blocked_url_fetcher,
            ).render()
            pdf_bytes = rendered.write_pdf()
        except RendererError:
            raise
        except Exception as exc:
            raise RendererError(f"weasyprint failed to render the document: {exc}") from exc

        if not pdf_bytes:
            raise RendererError("weasyprint produced an empty document")

        return RenderResult(pdf_bytes=pdf_bytes, page_count=len(rendered.pages))
