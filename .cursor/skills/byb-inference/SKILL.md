---
name: byb-inference
description: >-
  Own the Before You Buy AI enrichment path (inference-service): scrape listing
  context, call vLLM or heuristics, emit ProductProfile, forward SimulationMeasured.
  Use when editing services/inference-service, ProductProfile contracts, enrichment
  prompts, confidence/source tagging, or the simulation.requested → measured flow.
---

# Before You Buy — Inference (AI component)

## Ownership boundary

You own **product understanding** only:

`SimulationRequested` → scrape/notes/vision context → `ProductProfile` → `SimulationMeasured`

Do **not** change fit geometry rules (`geometry-service`) or gateway persistence unless a contract change requires it. Prefer extending `byb_common.contracts` carefully and updating all three services when fields change.

## Pipeline (source of truth)

```
api-gateway  --simulation.requested-->  inference-service :8002
                                              │
                          scrape product_link + shopper_notes
                          optional room image (vision only)
                                              │
                         Token Factory LLM  OR  heuristic fallback
                                              │
                     --simulation.measured-->  geometry-service
```

| Entry | File | Role |
| --- | --- | --- |
| `POST /v1/profile` | `services/inference-service/src/byb_inference/main.py` | Enrich only (Token Factory prove) |
| `POST /v1/enrich` | same | Sync enrich + forward to geometry |
| `POST /events` | same | Dapr sub for `simulation.requested` |
| Token Factory ops | `scripts/amd-layer-a.md` | Env wire, smoke, prove |
| `describe_product` | `.../vllm_client.py` | OpenAI-compatible Token Factory client |
| `extract_context` / `fallback_profile` | `.../products.py` | Scrape + heuristics |
| Contracts | `libs/byb-common/src/byb_common/contracts.py` | `ProductProfile`, events |

## Invariants (do not break)

1. **Always return a `ProductProfile`** from `enrich`. If Token Factory fails or is down, call `fallback_profile` — demos must complete without a GPU.
2. **Tag provenance**: `source="amd_token_factory"` (model read), `"catalog"` (published SKU box) or `"heuristic"`; mark each footprint axis in `dimension_reliability` as `extracted` / `verified` / `estimated` and set `measurement_basis`. Never leave an estimated axis unlabelled — the UI warns the shopper from it.
3. **Keep `confidence` in `[0, 1]`.** Today: Token Factory `0.72`, catalog `>= 0.6`, heuristic `0.25`–`0.45`. If you add real scores, still clamp and document.
4. **Dimensions in centimetres** on `ProductGeometry`; clamp with existing `MAX_DIMENSION_CM` (800). Geometry service expects cm and converts to metres.
5. **Forward after enrich**: publish `simulation.measured` via Dapr, else HTTP `geometry-service` `/v1/measure`. Do not POST results to the gateway from inference.
6. **Shared uploads**: read images only as `UPLOAD_DIR / Path(image_key).name` (basename only — no traversal).

## Contract checklist

When changing `ProductProfile` or event payloads:

- [ ] Update `libs/byb-common/src/byb_common/contracts.py`
- [ ] Update `vllm_client.to_profile` / `SYSTEM_PROMPT` JSON keys
- [ ] Update `products.fallback_profile`
- [ ] Update `frontend/src/lib/api.ts` types if the UI consumes new fields
- [ ] Run `poetry run test` in `services/inference-service`

## Related skills

- Prompt / parse / heuristic details → [byb-vllm-enrichment](../byb-vllm-enrichment/SKILL.md)
- Local run / GPU / smoke → [byb-ai-local-dev](../byb-ai-local-dev/SKILL.md)
