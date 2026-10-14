# Buy You Before - Inference Service

Turns a product URL (or a shopper's notes about a photo) into a real-world
`ProductProfile` with centimetre dimensions, using a vLLM OpenAI-compatible endpoint.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | model + transport status |
| POST | `/v1/enrich` | synchronous `SimulationRequested` -> `ProductProfile` |
| POST | `/events` | Dapr subscription target for `simulation.requested` |

## Degradation

When no vLLM endpoint answers, `products.fallback_profile` supplies category
heuristics at `confidence=0.25` and tags the profile `source="heuristic"`, so a demo
still completes end to end and the UI shows where the numbers came from.

## Poetry

```bash
poetry install
poetry run dev            # :8002
poetry run start
poetry run test
```

## AMD ROCm

The compose stack starts vLLM from the `vllm/vllm-openai-rocm` image under the `gpu`
profile. Point `VLLM_BASE_URL` at a managed/remote AMD instance instead and leave the
profile off to run this service without local GPUs.
