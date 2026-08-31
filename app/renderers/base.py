from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class RenderResult:
    """Rendered document plus the metadata the tool layer needs."""

    pdf_bytes: bytes
    page_count: int


class RendererError(Exception):
    """Base class for document-renderer failures."""


class RendererInputError(RendererError):
    """The supplied content could not be turned into a document."""


class RendererTimeoutError(RendererError):
    """The renderer did not finish within the allotted time."""


@runtime_checkable
class DocumentRenderer(Protocol):
    """Interface every PDF-rendering backend must implement.

    Implementations own their engine's setup and must translate engine
    failures into the ``RendererError`` hierarchy. They must not fetch remote
    resources referenced by the markdown.
    """

    name: str

    async def render(self, *, title: str, markdown_body: str) -> RenderResult: ...
