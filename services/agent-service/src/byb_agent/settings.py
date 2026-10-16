from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "agent-service"
    port: int = 8007
    log_level: str = "INFO"

    internal_token: str = "dev-internal-token"

    # The deterministic pipeline the agent drives.
    gateway_url: str = "http://localhost:8001"
    catalog_url: str = "http://localhost:8004"

    # Evolus workspace credentials. The same key serves the REST API and the chat endpoint.
    evolus_base_url: str = "https://api.evolus.ai"
    evolus_api_key: str = ""
    evolus_app_id: str = ""
    evolus_agent_id: str = ""
    evolus_workflow_id: str = ""
    evolus_library_id: str = ""
    # AI Tool that rewrites the reply. Empty means send the template as the agent wrote it.
    evolus_reply_tool: str = ""

    # The open model served on AMD hardware; agents need function calling, so Qwen + hermes parser.
    vllm_base_url: str = ""
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    vllm_api_key: str = ""

    # Where Evolus can reach this service, for workflow webhook callbacks.
    public_base_url: str = ""

    # Loop and fan-out boundaries of the fit search.
    max_candidates: int = 4
    parallel_fits: int = 2
    settle_timeout_s: int = 120
    poll_interval_s: float = 1.5
    # Below this the agent stops guessing and hands the case to a person.
    handoff_confidence: float = 0.35

    # A multi-piece brief is a bigger claim than a single fit, so it is capped and judged
    # against the same walkway the geometry engine uses.
    max_joint_pieces: int = 4
    max_joint_coverage: float = 0.6
    min_walkway_m: float = 0.6


settings = Settings()
