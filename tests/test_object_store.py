import pytest

from app.config import Settings
from app.storage import ObjectStore, ObjectStoreConfigError, get_object_store


def test_make_object_key_is_opaque_prefixed():
    key = ObjectStore.make_object_key("abc123", "Photosynthesis Explained.pdf")
    assert key == "abc123/photosynthesis-explained.pdf"


def test_make_object_key_strips_paths_and_unicode():
    key = ObjectStore.make_object_key("id1", "../../etc/Uber Straße Notes.pdf")
    assert key.startswith("id1/")
    assert key.endswith(".pdf")
    assert "/" not in key[len("id1/") :]


def test_make_object_key_falls_back_when_slug_is_empty():
    key = ObjectStore.make_object_key("id2", "___.pdf")
    assert key == "id2/document.pdf"


def test_get_object_store_requires_config(settings):
    settings.PDF_GENERATION_ENABLED = True
    settings.S3_ENDPOINT_URL = None
    with pytest.raises(ObjectStoreConfigError):
        get_object_store(settings)


def test_get_object_store_builds_when_configured(pdf_settings):
    store = get_object_store(pdf_settings)
    assert isinstance(store, ObjectStore)
    assert store.bucket == "learning-documents"


@pytest.mark.integration
async def test_minio_round_trip():
    import httpx

    settings = Settings()  # type: ignore[call-arg]
    if not settings.S3_ENDPOINT_URL or not settings.S3_ACCESS_KEY:
        pytest.skip("S3_* not configured for an integration run")

    store = get_object_store(settings)
    await store.open()
    try:
        if settings.S3_ENSURE_BUCKET:
            await store.ensure_bucket()

        key = store.make_object_key("itest", "round-trip.pdf")
        await store.put_pdf(key, b"%PDF-1.4 integration\n%%EOF")

        url = await store.presigned_get_url(
            key, filename="round trip.pdf", expires_in=120
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "attachment" in resp.headers.get("content-disposition", "")
    finally:
        await store.close()
