"""Dapr HTTP helpers with a direct-URL fallback so services also run under plain docker-compose."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("byb.dapr")

INTERNAL_TOKEN_HEADER = "x-byb-token"


class DaprTransport:
    """Resolves whether calls go through a daprd sidecar or straight to a service URL."""

    def __init__(self, dapr_http_endpoint: str | None, routes: dict[str, str], token: str) -> None:
        self._endpoint = dapr_http_endpoint.rstrip("/") if dapr_http_endpoint else None
        self._routes = routes
        self._token = token

    @property
    def via_dapr(self) -> bool:
        return self._endpoint is not None

    def url(self, app_id: str, method: str) -> str:
        if self._endpoint:
            return f"{self._endpoint}/v1.0/invoke/{app_id}/method/{method.lstrip('/')}"
        base = self._routes.get(app_id)
        if not base:
            raise RuntimeError(f"Neither DAPR_HTTP_ENDPOINT nor a direct URL is configured for {app_id!r}")
        return f"{base.rstrip('/')}/{method.lstrip('/')}"

    def headers(self) -> dict[str, str]:
        return {INTERNAL_TOKEN_HEADER: self._token}

    async def request(self, client: httpx.AsyncClient, app_id: str, method: str, payload: Any) -> httpx.Response:
        return await client.post(self.url(app_id, method), json=payload, headers=self.headers(), timeout=60)


async def publish_event(
    client: httpx.AsyncClient,
    dapr_http_endpoint: str | None,
    pubsub_name: str,
    topic: str,
    payload: Any,
) -> bool:
    if not dapr_http_endpoint:
        return False
    url = f"{dapr_http_endpoint.rstrip('/')}/v1.0/publish/{pubsub_name}/{topic}"
    response = await client.post(url, json=payload, timeout=30)
    response.raise_for_status()
    logger.info("published %s to %s/%s", topic, pubsub_name, topic)
    return True
