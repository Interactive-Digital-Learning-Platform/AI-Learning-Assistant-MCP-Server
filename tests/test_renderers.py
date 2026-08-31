import pytest

from app.renderers import RendererError, RenderResult, get_renderer
from tests.conftest import FakeRenderer


async def test_fake_renderer_contract(sample_markdown):
    renderer = FakeRenderer(page_count=4)
    result = await renderer.render(title="T", markdown_body=sample_markdown)

    assert isinstance(result, RenderResult)
    assert result.page_count == 4
    assert result.pdf_bytes


def test_get_renderer_unknown_name(settings):
    settings.PDF_RENDERER = "definitely-not-a-renderer"
    with pytest.raises(ValueError):
        get_renderer(settings)


def test_get_renderer_returns_weasyprint(pdf_settings):
    pytest.importorskip("weasyprint")
    renderer = get_renderer(pdf_settings)
    assert renderer.name == "weasyprint"


def test_blocked_url_fetcher_rejects_external_urls():
    from app.renderers.weasyprint import _blocked_url_fetcher

    with pytest.raises(RendererError):
        _blocked_url_fetcher("http://169.254.169.254/latest/meta-data/")


def test_blocked_url_fetcher_allows_data_uris():
    pytest.importorskip("weasyprint")
    from app.renderers.weasyprint import _blocked_url_fetcher

    result = _blocked_url_fetcher("data:text/plain;base64,aGVsbG8=")
    assert result


@pytest.mark.integration
async def test_weasyprint_renders_a_pdf(pdf_settings, sample_markdown):
    pytest.importorskip("weasyprint")
    renderer = get_renderer(pdf_settings)

    result = await renderer.render(title="Photosynthesis", markdown_body=sample_markdown)

    assert result.pdf_bytes.startswith(b"%PDF")
    assert result.page_count >= 1


@pytest.mark.integration
async def test_weasyprint_survives_external_resource_reference(pdf_settings, sample_markdown):
    pytest.importorskip("weasyprint")
    renderer = get_renderer(pdf_settings)
    body = sample_markdown + "\n\n![x](http://169.254.169.254/latest/meta-data/)\n"

    result = await renderer.render(title="SSRF", markdown_body=body)

    assert result.pdf_bytes.startswith(b"%PDF")
