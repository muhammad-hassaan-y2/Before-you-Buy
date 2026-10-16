"""OpenAI-compatible LLM client for AMD Token Factory.

Calls POST {VLLM_BASE_URL}/chat/completions with Bearer VLLM_API_KEY and VLLM_MODEL.
Base URL and model id must come from official Token Factory documentation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any

import httpx

from byb_common.contracts import ProductGeometry, ProductProfile
from byb_inference.settings import settings

logger = logging.getLogger("byb.inference.llm")

SYSTEM_PROMPT = (
    "You are a furniture specification extractor. Use ONLY the product evidence provided. "
    "Prefer assembled/product dimensions; ignore package, shipping, carton, and seat-only sizes "
    "for width_cm/depth_cm/height_cm footprints. "
    "Answer with a single JSON object and nothing else, using exactly these keys: "
    '{"name": str, "brand": str|null, "category": str, "material": str|null, "price_band": "low|mid|high"|null, '
    '"width_cm": number|null, "depth_cm": number|null, "height_cm": number|null, '
    '"clearance_cm": number|null, "summary": str}. '
    "Never invent measurements. If a dimension is not evidenced, set it to null and say so in summary. "
    "Cite which evidence you used in summary (e.g. JSON-LD, spec table, shopper notes)."
)

MAX_DIMENSION_CM = 800.0
PROVIDER_TOKEN_FACTORY = "amd_token_factory"
REQUIRED_DIM_KEYS = ("width_cm", "depth_cm", "height_cm")
RETRYABLE_STATUS = {429, 502, 503, 504}
NON_RETRYABLE_STATUS = {400, 401, 403, 404}
MAX_ATTEMPTS = 3


def chat_completions_url(base_url: str | None = None) -> str:
    root = (base_url if base_url is not None else settings.vllm_base_url).rstrip("/")
    return f"{root}/chat/completions"


def _scan_json(text: str) -> dict[str, Any] | None:
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


def _parse_required_dimension(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 1.0 or number > MAX_DIMENSION_CM:
        return None
    return number


def to_profile(payload: dict[str, Any], *, model_id: str | None = None) -> ProductProfile | None:
    """Validate model JSON then build ProductProfile. Returns None if required fields are missing."""
    name = str(payload.get("name") or "").strip()
    if not name:
        return None

    dims: dict[str, float] = {}
    for key in REQUIRED_DIM_KEYS:
        parsed = _parse_required_dimension(payload.get(key))
        if parsed is None:
            return None
        dims[key] = parsed

    clearance = _parse_required_dimension(payload.get("clearance_cm"))
    if clearance is None:
        clearance = 60.0
    clearance = min(clearance, 150.0)

    resolved_model = model_id if model_id is not None else settings.vllm_model
    reliability = {key: "extracted" for key in REQUIRED_DIM_KEYS}
    return ProductProfile(
        name=name[:120],
        brand=payload.get("brand"),
        category=str(payload.get("category") or "furniture")[:40],
        material=payload.get("material"),
        price_band=payload.get("price_band"),
        geometry=ProductGeometry(
            width_cm=dims["width_cm"],
            depth_cm=dims["depth_cm"],
            height_cm=dims["height_cm"],
            clearance_cm=clearance,
        ),
        confidence=0.72,
        summary=str(payload.get("summary") or "")[:400],
        source=PROVIDER_TOKEN_FACTORY,
        provider=PROVIDER_TOKEN_FACTORY,
        model=resolved_model or None,
        dimension_reliability=reliability,
        measurement_basis=PROVIDER_TOKEN_FACTORY,
    )


def build_messages(context: str, image_data_uri: str | None) -> list[dict[str, Any]]:
    user_text = f"Product context:\n{context or '(no listing text available)'}"
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


def _auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.vllm_api_key:
        headers["Authorization"] = f"Bearer {settings.vllm_api_key}"
    return headers


def _log_inference_event(**fields: Any) -> None:
    """Structured ops log — never includes API keys or raw shopper/context text."""
    payload = {
        "provider": PROVIDER_TOKEN_FACTORY,
        "model": settings.vllm_model or None,
        **fields,
    }
    logger.info("token_factory_inference %s", json.dumps(payload, default=str))


def _retry_delay_s(attempt: int, response: httpx.Response | None) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 8.0)
            except ValueError:
                pass
    base = 0.25 * (2**attempt)
    return min(base + random.uniform(0, 0.25), 8.0)


async def describe_product(
    client: httpx.AsyncClient, context: str, image_data_uri: str | None = None
) -> ProductProfile | None:
    """Ask AMD Token Factory for a product profile with bounded retries."""
    if not settings.llm_configured:
        _log_inference_event(success=False, failure_reason="not_configured", http_status=None, duration_ms=0)
        return None
    if not settings.vllm_base_url.strip().lower().startswith("https://"):
        _log_inference_event(success=False, failure_reason="base_url_not_https", http_status=None, duration_ms=0)
        logger.warning("VLLM_BASE_URL must be https:// for AMD Token Factory")
        return None

    body = {
        "model": settings.vllm_model,
        "messages": build_messages(context, image_data_uri),
        "temperature": 0,
        "max_tokens": settings.vllm_max_tokens,
    }
    url = chat_completions_url()
    started = time.perf_counter()
    deadline = started + max(settings.vllm_timeout_s * MAX_ATTEMPTS, settings.vllm_timeout_s + 5.0)
    last_status: int | None = None
    failure_reason = "unknown"

    for attempt in range(MAX_ATTEMPTS):
        if time.perf_counter() > deadline:
            failure_reason = "deadline_exceeded"
            break
        per_attempt_timeout = min(settings.vllm_timeout_s, max(1.0, deadline - time.perf_counter()))
        try:
            response = await client.post(
                url,
                json=body,
                headers=_auth_headers(),
                timeout=per_attempt_timeout,
            )
            last_status = response.status_code
            if response.status_code in NON_RETRYABLE_STATUS:
                failure_reason = f"http_{response.status_code}"
                _log_inference_event(
                    success=False,
                    failure_reason=failure_reason,
                    http_status=response.status_code,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    attempt=attempt + 1,
                )
                return None
            if response.status_code in RETRYABLE_STATUS:
                failure_reason = f"http_{response.status_code}"
                if attempt + 1 >= MAX_ATTEMPTS or time.perf_counter() > deadline:
                    break
                await asyncio.sleep(_retry_delay_s(attempt, response))
                continue
            response.raise_for_status()
        except httpx.TimeoutException:
            last_status = None
            failure_reason = "timeout"
            if attempt + 1 >= MAX_ATTEMPTS or time.perf_counter() > deadline:
                break
            await asyncio.sleep(_retry_delay_s(attempt, None))
            continue
        except httpx.TransportError:
            last_status = None
            failure_reason = "connection_error"
            if attempt + 1 >= MAX_ATTEMPTS or time.perf_counter() > deadline:
                break
            await asyncio.sleep(_retry_delay_s(attempt, None))
            continue
        except httpx.HTTPStatusError as exc:
            last_status = exc.response.status_code if exc.response is not None else None
            failure_reason = f"http_{last_status}"
            if last_status in RETRYABLE_STATUS and attempt + 1 < MAX_ATTEMPTS:
                await asyncio.sleep(_retry_delay_s(attempt, exc.response))
                continue
            _log_inference_event(
                success=False,
                failure_reason=failure_reason,
                http_status=last_status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                attempt=attempt + 1,
            )
            return None
        except (httpx.HTTPError, ValueError) as exc:
            failure_reason = type(exc).__name__
            _log_inference_event(
                success=False,
                failure_reason=failure_reason,
                http_status=last_status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                attempt=attempt + 1,
            )
            return None

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError):
            failure_reason = "invalid_response_shape"
            _log_inference_event(
                success=False,
                failure_reason=failure_reason,
                http_status=last_status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                attempt=attempt + 1,
            )
            return None

        if not isinstance(content, str):
            failure_reason = "non_string_content"
            _log_inference_event(
                success=False,
                failure_reason=failure_reason,
                http_status=last_status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                attempt=attempt + 1,
            )
            return None

        profile = to_profile(_scan_json(content) or {}, model_id=settings.vllm_model)
        if profile is None:
            failure_reason = "invalid_product_json"
            _log_inference_event(
                success=False,
                failure_reason=failure_reason,
                http_status=last_status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                attempt=attempt + 1,
            )
            return None

        _log_inference_event(
            success=True,
            failure_reason=None,
            http_status=last_status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            attempt=attempt + 1,
        )
        return profile

    _log_inference_event(
        success=False,
        failure_reason=failure_reason or "retries_exhausted",
        http_status=last_status,
        duration_ms=int((time.perf_counter() - started) * 1000),
        attempt=MAX_ATTEMPTS,
    )
    return None
