from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "geometry-service"
    app_id: str = "geometry-service"
    port: int = 8003
    log_level: str = "INFO"

    dapr_http_endpoint: str | None = None
    pubsub_name: str = "byb-pubsub"
    internal_token: str = "dev-internal-token"

    gateway_url: str = "http://localhost:8001"
    # Room side is metres; product side arrives in centimetres.
    min_walkway_m: float = 0.6
    wall_padding_m: float = 0.05


settings = Settings()
