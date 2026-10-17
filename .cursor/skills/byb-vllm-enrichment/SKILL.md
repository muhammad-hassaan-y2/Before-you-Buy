---
name: byb-vllm-enrichment
description: >-
  Improve Buy You Before listing scrape, vLLM prompts, JSON parsing, vision
  messages, and category heuristic fallbacks that produce ProductProfile.
  Use when changing vllm_client.py, products.py, SYSTEM_PROMPT, HEURISTICS,
  confidence scoring, scraped dimension extraction, or VLLM_SUPPORTS_VISION.
---

# vLLM enrichment & heuristics

## Files

| File | Change here when… |
| --- | --- |
| `services/inference-service/src/byb_inference/vllm_client.py` | Prompt, messages, JSON scan, `to_profile`, confidence |
| `services/inference-service/src/byb_inference/products.py` | Scrape regexes, `HEURISTICS`, `fallback_profile` |
| `services/inference-service/src/byb_inference/settings.py` | Timeouts, model id, vision flag |
| `services/inference-service/tests/test_products.py` | Unit coverage for parse/heuristics/`to_profile` |

## Prompt contract

`SYSTEM_PROMPT` must keep the model answering **one JSON object** with exactly:

```json
{
  "name": "str",
  "brand": "str|null",
  "category": "str",
  "material": "str|null",
  "price_band": "low|mid|high|null",
  "width_cm": 0,
  "depth_cm": 0,
  "height_cm": 0,
  "clearance_cm": 0,
  "summary": "str"
}
```

`to_profile` maps that into `ProductProfile` + `ProductGeometry`. Reject empty `name` (return `None` so caller falls back).

Parse completions with `_scan_json` (first balanced `{...}`) — models often wrap JSON in prose.

## Vision rules

- The product read is text-only today: the listing page is the only source of a product picture,
  and `describe_product` is called without one.
- Uploaded images are **room photos**. vision-service measures them; inference must never pass one
  to the model as product evidence.
- `build_messages` switches to multimodal `image_url` when a data URI is present, for the day a real
  product image exists. Keep it that way: gate on the image argument, not on a shopper upload.

## Heuristic fallback rules

- Trigger only when `describe_product` returns `None` (endpoint down, bad HTTP, unparseable JSON).
- Always set `source="heuristic"`. Confidence: `0.45` when `parse_dimensions` finds listing sizes, else `0.25`.
- `parse_dimensions(context)` must win over `HEURISTICS` for any axis it finds (width/depth/height in cm/mm/m).
- When adding a `HEURISTICS` category: key = lowercase phrase matched via `in` on lowered text; values = `(width, depth, height, clearance)` cm, realistic for that furniture type.

## Quality bar for AI changes

1. Add/extend tests in `tests/test_products.py` for any new parse or heuristic behaviour.
2. Prefer mocked httpx responses over requiring a live vLLM for unit tests.
3. Never silently invent high confidence when using category tables.
4. Prefer extracting numeric dims from listing text over category averages when both exist.
5. Keep scrape timeout and User-Agent via settings; do not hardcode.

## Security notes (enrichment)

- `product_link` is attacker-controlled: treat scrape as untrusted HTML; do not execute scripts; limit context size (already capped ~2500 chars).
- Do not follow `image_key` path segments — basename only under `UPLOAD_DIR`.
- Do not log full listing HTML or API keys.
