from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "vision-service"
    app_id: str = "vision-service"
    port: int = 8005
    log_level: str = "INFO"

    dapr_http_endpoint: str | None = None
    pubsub_name: str = "byb-pubsub"
    internal_token: str = "dev-internal-token"

    geometry_url: str = "http://localhost:8003"
    gateway_url: str = "http://localhost:8001"

    # Shared with api-gateway, which writes the upload and names the key.
    upload_dir: str = "uploads"

    # Below this the photo is ignored and the shopper's own dimensions stand.
    min_confidence: float = 0.45
    max_obstacles: int = 4


settings = Settings()
