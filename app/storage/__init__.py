from app.config import Settings
from app.storage.base import ObjectStoreConfigError, ObjectStoreError
from app.storage.object_store import ObjectStore

__all__ = [
    "ObjectStore",
    "ObjectStoreConfigError",
    "ObjectStoreError",
    "get_object_store",
]


def get_object_store(settings: Settings) -> ObjectStore:
    """Build the object store from ``S3_*`` settings.

    Raises :class:`ObjectStoreConfigError` when the feature is on but storage is
    not configured. Only called when ``PDF_GENERATION_ENABLED`` is true.
    """
    missing = [
        name
        for name, value in (
            ("S3_ENDPOINT_URL", settings.S3_ENDPOINT_URL),
            ("S3_ACCESS_KEY", settings.S3_ACCESS_KEY),
            ("S3_SECRET_KEY", settings.S3_SECRET_KEY),
        )
        if not value
    ]
    if missing:
        raise ObjectStoreConfigError(
            f"object storage is not configured: missing {', '.join(missing)}"
        )

    return ObjectStore(
        bucket=settings.S3_BUCKET,
        endpoint_url=settings.S3_ENDPOINT_URL,
        public_endpoint_url=settings.S3_PUBLIC_ENDPOINT_URL,
        access_key=settings.S3_ACCESS_KEY.get_secret_value(),
        secret_key=settings.S3_SECRET_KEY.get_secret_value(),
        region=settings.S3_REGION,
        addressing_style=settings.S3_ADDRESSING_STYLE,
        ensure_bucket=settings.S3_ENSURE_BUCKET,
    )
