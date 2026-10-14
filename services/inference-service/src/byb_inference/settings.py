from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "inference-service"
    app_id: str = "inference-service"
    port: int = 8002
    log_level: str = "INFO"

    dapr_http_endpoint: str | None = None
    pubsub_name: str = "byb-pubsub"
    internal_token: str = "dev-internal-token"

    geometry_url: str = "http://localhost:8003"

    # AMD ROCm vLLM endpoint (OpenAI-compatible). Override per cloud deployment.
    vllm_base_url: str = "http://vllm:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-3B-Instruct"
    vllm_api_key: str = ""
    vllm_timeout_s: float = 25.0
    vllm_max_tokens: int = 512

    scrape_timeout_s: float = 12.0
    user_agent: str = "BuyYouBeforeBot/0.1 (+https://github.com/muhammad-hassaan-y2/Before-you-Buy)"

    # Set true when VLLM_MODEL is a vision model (e.g. Qwen2.5-VL) and room photos can be read.
    vllm_supports_vision: bool = False
    upload_dir: str = "/uploads"


settings = Settings()
