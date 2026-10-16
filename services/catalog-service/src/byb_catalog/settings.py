from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "catalog-service"
    app_id: str = "catalog-service"
    port: int = 8004
    log_level: str = "INFO"

    dapr_http_endpoint: str | None = None
    pubsub_name: str = "byb-pubsub"
    internal_token: str = "dev-internal-token"

    inference_url: str = "http://localhost:8002"
    gateway_url: str = "http://localhost:8001"

    # Below this, report no match and let inference-service read the listing itself.
    min_match_score: float = 0.34


settings = Settings()
