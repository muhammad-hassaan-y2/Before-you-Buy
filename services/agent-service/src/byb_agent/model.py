"""The team's own model: an open model served on AMD hardware behind a vLLM
OpenAI-compatible endpoint.

Used for the reading the agent does about a shopper's words - what they want, for which
room, at what budget. It never decides anything on its own: it fills a schema, and when it
disagrees with the shopper's own numbers the numbers win.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from byb_agent.settings import Settings

logger = logging.getLogger("byb.model")

JSON_ONLY = "Answer with one JSON object and nothing else. No prose, no markdown fences."


class AMDModel:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    @property
    def configured(self) -> bool:
        return bool(self._settings.vllm_base_url)

    @property
    def name(self) -> str:
        return self._settings.vllm_model if self.configured else ""

    async def complete(self, prompt: str, *, system: str = JSON_ONLY, max_tokens: int = 512) -> str:
        if not self.configured:
            raise RuntimeError("no AMD model endpoint configured: set VLLM_BASE_URL")
        url = f"{self._settings.vllm_base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._settings.vllm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.vllm_api_key}"
        body = {
            "model": self._settings.vllm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        response = await self._client.post(url, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        choices = response.json().get("choices") or []
        return str(((choices[0] if choices else {}).get("message") or {}).get("content", ""))

    async def read_json(self, prompt: str) -> dict[str, Any] | None:
        """Ask for a JSON object. `None` means the model was absent or unreadable, and the caller
        must fall back - never a silently empty dict."""
        if not self.configured:
            return None
        try:
            text = await self.complete(prompt)
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("amd model unavailable: %s", exc)
            return None
        return extract_json(text)


def extract_json(text: str) -> dict[str, Any] | None:
    """Models wrap JSON in prose or fences often enough that a bare json.loads is not enough."""
    if not text:
        return None
    for candidate in (text, _fenced(text), _braced(text)):
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _fenced(text: str) -> str | None:
    match = re.search(r"```(?:json)?\s*(.+?)```", text, flags=re.S)
    return match.group(1).strip() if match else None


def _braced(text: str) -> str | None:
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        return text[start : end + 1]
    return None
