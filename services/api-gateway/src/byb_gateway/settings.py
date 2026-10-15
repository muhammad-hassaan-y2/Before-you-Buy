from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "api-gateway"
    app_id: str = "api-gateway"
    port: int = 8001
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/beforeyoubuy"

    # When set, calls are routed through a daprd sidecar; otherwise the direct URLs below are used.
    dapr_http_endpoint: str | None = None
    pubsub_name: str = "byb-pubsub"
    internal_token: str = "dev-internal-token"

    # Head of the worker chain; every later hop is addressed by the workers themselves.
    catalog_url: str = "http://localhost:8004"

    upload_dir: str = "/uploads"
    max_upload_mb: int = 12
    allowed_origins: str = "http://localhost:3000"

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
