# Layer A — AMD Token Factory deployment readiness

Before You Buy’s inference-service calls an **AMD Token Factory** OpenAI-compatible
`/chat/completions` endpoint over **HTTPS**. This is not self-hosted vLLM.

## Docker Compose

`inference-service` receives from host `.env`:

- `VLLM_BASE_URL`
- `VLLM_MODEL`
- `VLLM_API_KEY`
- `VLLM_TIMEOUT_S`

## Configure credentials

Paste values **only** from your Token Factory UI / AMD docs:

```powershell
cd d:\hackathon
.\scripts\wire-amd-vllm.ps1 -BaseUrl "https://YOUR_TF_BASE/v1" -Model "YOUR_MODEL_ID" -ApiKey "YOUR_KEY"
```

## Start services (PowerShell)

```powershell
cd d:\hackathon
docker compose up -d postgres redis

# Terminal A — api-gateway
cd d:\hackathon\services\api-gateway
poetry run dev

# Terminal B — inference (loads repo-root .env)
cd d:\hackathon\services\inference-service
# If using the project venv instead of poetry:
#   $env:PYTHONPATH="d:\hackathon\services\inference-service\src;d:\hackathon\libs\byb-common\src"
#   .\.venv\Scripts\python.exe -m uvicorn byb_inference.main:app --host 0.0.0.0 --port 8002 --reload
poetry run dev

# Terminal C — geometry
cd d:\hackathon\services\geometry-service
poetry run dev

# Terminal D — frontend (optional for UI)
cd d:\hackathon\frontend
pnpm dev
```

Or with Compose for the three Python services + frontend (after `.env` is filled):

```powershell
cd d:\hackathon
docker compose up --build -d api-gateway inference-service geometry-service frontend
```

## Verify live inference

```powershell
cd d:\hackathon
Invoke-RestMethod http://localhost:8002/healthz   # llm_configured=true
.\scripts\amd-vllm-smoke.ps1                      # direct Token Factory chat
.\scripts\prove-amd-vllm.ps1                      # must return source=amd_token_factory
```

`prove-amd-vllm.ps1` **fails** if the profile is `heuristic` — that is not AMD proof.

## Security notes

- Scripts never print `VLLM_API_KEY`.
- Smoke detects HTTP 401/403 as authentication failure.
- Keep secrets in local `.env` (gitignored).
