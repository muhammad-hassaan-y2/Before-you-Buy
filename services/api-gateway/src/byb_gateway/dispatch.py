"""Fan-out from the gateway to the worker services.

Dapr pub/sub is the preferred transport. Without a sidecar the gateway calls the
same methods over direct HTTP so `docker compose up` still works in dev.
"""

from __future__ import annotations

import logging

import httpx

from byb_common.contracts import SimulationRequested
from byb_common.dapr import DaprTransport, publish_event
from byb_gateway.settings import settings

logger = logging.getLogger("byb.gateway.dispatch")

TOPIC_REQUESTED = "simulation.requested"


class Dispatcher:
    def __init__(self, client: httpx.AsyncClient, transport: DaprTransport) -> None:
        self._client = client
        self._transport = transport

    async def start(self, message: SimulationRequested) -> None:
        if await publish_event(
            self._client, settings.dapr_http_endpoint, settings.pubsub_name, TOPIC_REQUESTED, message.model_dump()
        ):
            return
        logger.info("no daprd sidecar, invoking inference-service directly")
        response = await self._transport.request(self._client, "inference-service", "/v1/enrich", message.model_dump())
        response.raise_for_status()
