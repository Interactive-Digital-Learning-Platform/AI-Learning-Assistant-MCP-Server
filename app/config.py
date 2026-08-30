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


settings = Settings()  # type: ignore[call-arg]
