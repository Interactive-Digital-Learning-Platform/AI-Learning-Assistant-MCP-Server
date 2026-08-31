import logging
import re
from pathlib import Path
from urllib.parse import quote

from app.storage.base import ObjectStoreError

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")[:80]


def _content_disposition(filename: str) -> str:
    ascii_name = (
        filename.encode("ascii", "ignore").decode("ascii").replace('"', "").replace("\\", "")
        or "document.pdf"
    )
    disposition = f'attachment; filename="{ascii_name}"'
    if ascii_name != filename:
        disposition += f"; filename*=UTF-8''{quote(filename, safe='')}"
    return disposition


class ObjectStore:
    """S3-compatible object store for generated PDFs (Cloudflare R2 or MinIO).

    Uploads go through the internal endpoint; presigned download URLs are signed
    against the public endpoint so the URL host is reachable by the end user.
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        public_endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        region: str,
        addressing_style: str = "path",
        ensure_bucket: bool = False,
    ) -> None:
        self.bucket = bucket
        self._endpoint_url = endpoint_url
        self._public_endpoint_url = public_endpoint_url or endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._addressing_style = addressing_style
        self._ensure_bucket_flag = ensure_bucket

        self._session = None
        self._client_ctx = None
        self._presign_ctx = None
        self._client = None
        self._presign_client = None

    def _build_config(self):
        from botocore.config import Config

        return Config(
            signature_version="s3v4",
            s3={"addressing_style": self._addressing_style},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
            max_pool_connections=5,
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        )

    async def open(self) -> None:
        import aioboto3

        self._session = aioboto3.Session()
        config = self._build_config()

        self._client_ctx = self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
            config=config,
        )
        self._client = await self._client_ctx.__aenter__()

        if self._public_endpoint_url == self._endpoint_url:
            self._presign_client = self._client
        else:
            self._presign_ctx = self._session.client(
                "s3",
                endpoint_url=self._public_endpoint_url,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
                config=config,
            )
            self._presign_client = await self._presign_ctx.__aenter__()

        logger.info(
            "object store opened",
            extra={
                "endpoint": self._endpoint_url,
                "public_endpoint": self._public_endpoint_url,
                "bucket": self.bucket,
            },
        )

    async def close(self) -> None:
        if self._presign_ctx is not None:
            await self._presign_ctx.__aexit__(None, None, None)
        if self._client_ctx is not None:
            await self._client_ctx.__aexit__(None, None, None)
        self._client = None
        self._presign_client = None
        self._presign_ctx = None
        self._client_ctx = None

    @property
    def _s3(self):
        if self._client is None:
            raise ObjectStoreError("ObjectStore.open() was not called")
        return self._client

    async def ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            await self._s3.head_bucket(Bucket=self.bucket)
            logger.info("object store bucket present", extra={"bucket": self.bucket})
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchBucket"):
                await self._s3.create_bucket(Bucket=self.bucket)
                logger.info("object store bucket created", extra={"bucket": self.bucket})
            else:
                raise

    @staticmethod
    def make_object_key(document_id: str, filename: str) -> str:
        slug = _slug(Path(filename).stem) or "document"
        return f"{document_id}/{slug}.pdf"

    async def put_pdf(self, key: str, data: bytes) -> None:
        await self._s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/pdf",
        )

    async def presigned_get_url(self, key: str, *, filename: str, expires_in: int) -> str:
        client = self._presign_client or self._s3
        return await client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentType": "application/pdf",
                "ResponseContentDisposition": _content_disposition(filename),
            },
            ExpiresIn=expires_in,
        )
