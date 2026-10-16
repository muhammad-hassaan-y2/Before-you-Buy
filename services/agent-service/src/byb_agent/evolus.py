"""Evolus clients: the REST API for workflows, AI Tools and libraries, plus the
OpenAI-compatible endpoint for agent chat.

Nothing here is required to be configured. Every call raises `EvolusError` and the caller
decides whether to degrade; that keeps the demo runnable before the workspace credentials
exist and honest about which brain answered.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from byb_agent.settings import Settings

logger = logging.getLogger("byb.evolus")

REST = "/api/v1"
CHAT = "/v1"


class EvolusError(RuntimeError):
    """Evolus refused, or could not be reached."""


class Evolus:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    @property
    def base(self) -> str:
        return self._settings.evolus_base_url.rstrip("/")

    @property
    def credentials(self) -> bool:
        return bool(self._settings.evolus_api_key and self._settings.evolus_app_id)

    @property
    def agent_model(self) -> str | None:
        """The `model` string the OpenAI-compatible endpoint expects: <applicationId>:<agentId>."""
        if not self.credentials or not self._settings.evolus_agent_id:
            return None
        return f"{self._settings.evolus_app_id}:{self._settings.evolus_agent_id}"

    def headers(self) -> dict[str, str]:
        return {"X-ApiKey": self._settings.evolus_api_key, "X-Application-Id": self._settings.evolus_app_id}

    async def _call(self, method: str, path: str, *, json: Any = None, data: Any = None, files: Any = None, timeout: float = 60) -> httpx.Response:
        if not self.credentials:
            raise EvolusError("Evolus is not configured: set EVOLUS_API_KEY and EVOLUS_APP_ID")
        try:
            response = await self._client.request(
                method, f"{self.base}{path}", headers=self.headers(), json=json, data=data, files=files, timeout=timeout
            )
        except httpx.HTTPError as exc:
            raise EvolusError(f"evolus request failed: {exc}") from exc
        if response.status_code == 402:
            raise EvolusError("Evolus workspace credits are exhausted")
        if response.status_code >= 400:
            raise EvolusError(f"evolus {method} {path} -> {response.status_code}: {response.text[:200]}")
        return response

    async def ask(self, prompt: str, *, system: str | None = None, conversation_id: str | None = None) -> tuple[str, str | None]:
        """One turn with the Evolus agent. Returns the reply and the conversation id to continue with."""
        model = self.agent_model
        if model is None:
            raise EvolusError("no agent id: set EVOLUS_AGENT_ID")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        headers = {"Authorization": f"Bearer {self._settings.evolus_api_key}", "Content-Type": "application/json"}
        if conversation_id:
            headers["X-Conversation-Id"] = conversation_id
        try:
            response = await self._client.post(
                f"{self.base}{CHAT}/chat/completions", headers=headers, json={"model": model, "messages": messages}, timeout=90
            )
        except httpx.HTTPError as exc:
            raise EvolusError(f"evolus chat failed: {exc}") from exc
        if response.status_code >= 400:
            raise EvolusError(f"evolus chat -> {response.status_code}: {response.text[:200]}")
        payload = response.json()
        text = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        return text, response.headers.get("x-conversation-id")

    def stream_chat(self, model: str, messages: list[dict[str, Any]], conversation_id: str | None) -> Any:
        """Open a streaming chat request. The caller owns the response, so the UI can be fed SSE."""
        if not self.credentials:
            raise EvolusError("Evolus is not configured: set EVOLUS_API_KEY and EVOLUS_APP_ID")
        headers = {"Authorization": f"Bearer {self._settings.evolus_api_key}", "Content-Type": "application/json"}
        if conversation_id:
            headers["X-Conversation-Id"] = conversation_id
        return self._client.stream(
            "POST", f"{self.base}{CHAT}/chat/completions", headers=headers, json={"model": model, "messages": messages, "stream": True}
        )

    async def list_models(self) -> list[dict[str, Any]]:
        response = await self._client.get(f"{self.base}{CHAT}/models", headers={"Authorization": f"Bearer {self._settings.evolus_api_key}"}, timeout=30)
        if response.status_code >= 400:
            raise EvolusError(f"evolus models -> {response.status_code}")
        return list(response.json().get("data") or [])

    async def execute_workflow(
        self,
        workflow_id: str,
        text: str,
        *,
        params: dict[str, Any] | None = None,
        files: dict[str, tuple] | None = None,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        """Start a workflow; Evolus answers 202 with the execution id and the run happens there.

        Multipart always, because the endpoint is documented that way and a room photo rides in
        the same request as the shopper's words.
        """
        parts: list[tuple[str, tuple]] = [("input", (None, text))]
        if params:
            parts.append(("parameters", (None, json.dumps(params))))
        if callback_url:
            parts.append(("callbackUrl", (None, callback_url)))
        parts.extend((name, part) for name, part in (files or {}).items())
        response = await self._call("POST", f"{REST}/workflows/{workflow_id}/execute", files=parts, timeout=60)
        return response.json()

    async def workflow_execution(self, workflow_id: str, execution_id: str) -> dict[str, Any]:
        response = await self._call("GET", f"{REST}/workflows/{workflow_id}/executions/{execution_id}", timeout=30)
        return response.json()

    async def run_tool(self, tool: str, text: str, options: dict[str, Any] | None = None) -> str:
        """One of the eleven ready-made AI Tools: document to data, translate, summarise, write an email."""
        response = await self._call("POST", f"{REST}/ai-tools/{tool}/run", json={"text": text, "options": options or {}}, timeout=90)
        return str(response.json().get("output", ""))

    async def index_document(self, library_id: str, name: str, content: bytes) -> dict[str, Any]:
        response = await self._call(
            "POST", f"{REST}/memories/{library_id}/documents?language=en", files={"file": (name, content, "text/markdown")}, timeout=60
        )
        return response.json()

