"""vLLM client. Speaks the OpenAI-compatible API that `vllm serve` exposes, so an AMD
ROCm instance in the compose stack and any hosted vLLM endpoint are interchangeable."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from byb_common.contracts import ProductGeometry, ProductProfile
from byb_inference.settings import settings

logger = logging.getLogger("byb.inference.vllm")

SYSTEM_PROMPT = (
    "You are a furniture specification extractor. From the product context below, infer the physical "
    "size of the item and the walkway a shopper needs around it, in centimetres. "
    "Answer with a single JSON object and nothing else, using exactly these keys: "
    '{"name": str, "brand": str|null, "category": str, "material": str|null, "price_band": "low|mid|high"|null, '
    '"width_cm": number, "depth_cm": number, "height_cm": number, "clearance_cm": number, "summary": str}. '
    "Use realistic values for the category when the listing is silent, and say so in summary."
)

MAX_DIMENSION_CM = 800.0


def _scan_json(text: str) -> dict[str, Any] | None:
    """Return the first balanced JSON object in a noisy model completion."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def _dimension(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, 1.0), MAX_DIMENSION_CM)


def to_profile(payload: dict[str, Any]) -> ProductProfile | None:
    name = str(payload.get("name") or "").strip()
    if not name:
        return None
    geometry = ProductGeometry(
        width_cm=_dimension(payload.get("width_cm"), 100),
        depth_cm=_dimension(payload.get("depth_cm"), 60),
        height_cm=_dimension(payload.get("height_cm"), 80),
        clearance_cm=min(_dimension(payload.get("clearance_cm"), 60), 150),
    )
    return ProductProfile(
        name=name[:120],
        brand=payload.get("brand"),
        category=str(payload.get("category") or "furniture")[:40],
        material=payload.get("material"),
        price_band=payload.get("price_band"),
        geometry=geometry,
        confidence=0.72,
        summary=str(payload.get("summary") or "")[:400],
        source="vllm",
    )


def build_messages(context: str, image_data_uri: str | None) -> list[dict[str, Any]]:
    user_text = f"Product context:\n{context or '(no listing text available)'}\n\nShopper notes:"
    if image_data_uri:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": image_data_uri}},
                ],
            },
        ]
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_text}]


async def describe_product(
    client: httpx.AsyncClient, context: str, image_data_uri: str | None = None
) -> ProductProfile | None:
    """Ask vLLM for a product profile. Returns None when the endpoint is absent or unwell."""
    headers = {"Content-Type": "application/json"}
    if settings.vllm_api_key:
        headers["Authorization"] = f"Bearer {settings.vllm_api_key}"
    body = {
        "model": settings.vllm_model,
        "messages": build_messages(context, image_data_uri),
        "temperature": 0,
        "max_tokens": settings.vllm_max_tokens,
    }
    try:
        response = await client.post(
            f"{settings.vllm_base_url.rstrip('/')}/chat/completions",
            json=body,
            headers=headers,
            timeout=settings.vllm_timeout_s,
        )
        response.raise_for_status()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("vLLM unavailable at %s: %s", settings.vllm_base_url, exc)
        return None

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning("vLLM returned an unexpected body shape")
        return None
    profile = to_profile(_scan_json(content) or {})
    if profile is None:
        logger.warning("vLLM completion was not parseable as a product JSON object")
    return profile
