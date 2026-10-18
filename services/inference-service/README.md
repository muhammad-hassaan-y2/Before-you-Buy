# Before You Buy - Inference Service

Turns a product URL (or a shopper's notes about a photo) into a real-world
`ProductProfile` with centimetre dimensions, using an **AMD Token Factory**
OpenAI-compatible chat endpoint (`VLLM_BASE_URL` / `VLLM_API_KEY` / `VLLM_MODEL`).

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | model, `llm_configured`, transport |
| POST | `/v1/profile` | enrich only (Token Factory prove; no geometry forward) |
| POST | `/v1/enrich` | synchronous `SimulationRequested` -> `ProductProfile` + forward |
| POST | `/events` | Dapr subscription target for `simulation.requested` |

Token Factory wiring: see `scripts/amd-layer-a.md`. Paste base URL and model id only from official Token Factory documentation.

## Degradation

Successful enrichments set `source` / `provider` to `amd_token_factory` and
`model` to `VLLM_MODEL`. When Token Factory is unset, unauthorized, times out,
or returns invalid JSON, `fallback_profile` uses listing/category heuristics
with `source="heuristic"`.

## Poetry

```bash
poetry install
poetry run dev            # :8002
poetry run start
poetry run test
```
