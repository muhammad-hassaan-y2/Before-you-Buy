from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Runtime config. LLM calls use an OpenAI-compatible AMD Token Factory endpoint.

    Set VLLM_BASE_URL, VLLM_API_KEY, and VLLM_MODEL from official Token Factory
    documentation after the team key is revealed. Do not invent hostnames or model ids.
    """

    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "inference-service"
    app_id: str = "inference-service"
    port: int = 8002
    log_level: str = "INFO"

    dapr_http_endpoint: str | None = None
    pubsub_name: str = "byb-pubsub"
    internal_token: str = "dev-internal-token"

    vision_url: str = "http://localhost:8005"
    gateway_url: str = "http://localhost:8001"

    # OpenAI-compatible chat API (AMD Token Factory). Env names kept for compatibility.
    # Leave empty until Token Factory docs provide the official base URL and model id.
    vllm_base_url: str = ""
    vllm_model: str = ""
    vllm_api_key: str = ""
    vllm_timeout_s: float = 60.0
    vllm_max_tokens: int = 512

    scrape_timeout_s: float = 12.0
    user_agent: str = "BuyYouBeforeBot/0.1 (+https://github.com/muhammad-hassaan-y2/Before-you-Buy)"

    @property
    def llm_configured(self) -> bool:
        return bool(self.vllm_base_url.strip() and self.vllm_model.strip() and self.vllm_api_key.strip())


settings = Settings()
