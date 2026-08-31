from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8006
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # --- Service-to-service auth ---
    # Shared secret with the AI Learning Assistant (its MCP_SERVER_AUTH_TOKEN).
    MCP_AUTH_TOKEN: SecretStr

    # --- Web search ---
    SEARCH_PROVIDER: str = "tavily"
    WEB_SEARCH_DEFAULT_MAX_RESULTS: int = 5
    WEB_SEARCH_MAX_RESULTS_LIMIT: int = 10
    WEB_SEARCH_TIMEOUT_SECONDS: float = 15.0
    WEB_SEARCH_PROVIDER_MAX_RETRIES: int = 2
    WEB_SEARCH_RATE_LIMIT_PER_MIN: int = 60

    # --- Provider: Tavily ---
    TAVILY_API_KEY: SecretStr | None = None
    TAVILY_SEARCH_DEPTH: str = "basic"  # basic | advanced

    # --- PDF generation ---
    PDF_GENERATION_ENABLED: bool = False
    PDF_RENDERER: str = "weasyprint"  # weasyprint | fpdf
    PDF_RENDER_TIMEOUT_SECONDS: float = 20.0
    PDF_UPLOAD_TIMEOUT_SECONDS: float = 15.0
    PDF_MARKDOWN_MAX_CHARS: int = 50_000
    PDF_MAX_PAGE_COUNT: int = 50
    PDF_URL_EXPIRES_SECONDS: int = 3600
    PDF_GENERATION_RATE_LIMIT_PER_MIN: int = 20

    # --- Object storage (S3-compatible: Cloudflare R2 in prod, MinIO locally) ---
    S3_ENDPOINT_URL: str | None = None
    S3_PUBLIC_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: SecretStr | None = None
    S3_SECRET_KEY: SecretStr | None = None
    S3_BUCKET: str = "learning-documents"
    S3_REGION: str = "us-east-1"  # "auto" for R2
    S3_ADDRESSING_STYLE: str = "path"
    S3_ENSURE_BUCKET: bool = False


settings = Settings()  # type: ignore[call-arg]
