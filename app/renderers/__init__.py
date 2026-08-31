import importlib.util

from app.config import Settings
from app.renderers.base import (
    DocumentRenderer,
    RendererError,
    RendererInputError,
    RendererTimeoutError,
    RenderResult,
)

__all__ = [
    "DocumentRenderer",
    "RenderResult",
    "RendererError",
    "RendererInputError",
    "RendererTimeoutError",
    "get_renderer",
]


def get_renderer(settings: Settings) -> DocumentRenderer:
    """Build the configured document renderer.

    Add a backend by implementing :class:`DocumentRenderer` and wiring a branch
    here keyed on ``PDF_RENDERER``. The engine import stays lazy so importing
    this package never requires the rendering libraries to be installed.
    """
    name = settings.PDF_RENDERER.strip().lower()

    if name == "weasyprint":
        if importlib.util.find_spec("weasyprint") is None:
            raise RendererError(
                "PDF_RENDERER='weasyprint' but the weasyprint package is not installed"
            )
        from app.renderers.weasyprint import WeasyPrintRenderer

        return WeasyPrintRenderer()

    raise ValueError(f"Unknown PDF_RENDERER: {settings.PDF_RENDERER!r}")
