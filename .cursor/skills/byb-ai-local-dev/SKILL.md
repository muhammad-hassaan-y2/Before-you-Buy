---
name: byb-ai-local-dev
description: >-
  Run and verify the Before You Buy AI path locally with AMD Token Factory
  (OpenAI-compatible VLLM_* env) or heuristic fallback. Use when starting
  inference, configuring Token Factory credentials, or validating enrich.
---

# AI path — local development

## Fast path (heuristics)

Leave `VLLM_BASE_URL` / `VLLM_MODEL` / `VLLM_API_KEY` empty until Token Factory values are known.

```bash
docker compose up -d postgres redis
cd services/inference-service && poetry run dev   # or venv
```

## AMD Token Factory

Values must come from official Token Factory / User Manual only — never invent hosts or model ids.

```env
VLLM_BASE_URL=<official-base-url>
VLLM_MODEL=<official-model-id>
VLLM_API_KEY=<team-api-key>
VLLM_TIMEOUT_S=60
```

```powershell
.\scripts\wire-amd-vllm.ps1 -BaseUrl "..." -Model "..." -ApiKey "..."
.\scripts\amd-vllm-smoke.ps1
.\scripts\prove-amd-vllm.ps1
```

See [scripts/amd-layer-a.md](../../../scripts/amd-layer-a.md).

`ProductProfile.source` is `amd_token_factory` on success, with `provider`, `model`,
`dimension_reliability` and `measurement_basis` alongside it; this is **not** self-hosted vLLM.

## Inference commands

```bash
cd services/inference-service
poetry run test
poetry run dev
curl -s localhost:8002/healthz   # llm_configured true|false
```

- `POST /v1/profile` — enrich only  
- `POST /v1/enrich` — enrich + geometry forward  
