from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "scene-service"
    app_id: str = "scene-service"
    port: int = 8006
    log_level: str = "INFO"

    dapr_http_endpoint: str | None = None
    pubsub_name: str = "byb-pubsub"
    internal_token: str = "dev-internal-token"

    gateway_url: str = "http://localhost:8001"

    # The glTF document travels inside the result callback, so it has a size ceiling.
    max_parts: int = 40


settings = Settings()
