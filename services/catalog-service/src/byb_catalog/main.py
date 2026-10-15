"""Catalog worker: resolves a product link or shopper notes into a known SKU and hands
the enriched request to inference-service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request

from byb_catalog.matching import candidate_for
from byb_catalog.settings import settings
from byb_catalog.skus import CATALOG
from byb_common.contracts import CatalogCandidate, SimulationCatalogued, SimulationRequested, SimulationStatus
from byb_common.dapr import DaprTransport, publish_event

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.catalog")

TOPIC_REQUESTED = "simulation.requested"
TOPIC_CATALOGUED = "simulation.catalogued"
PROGRESS_METHOD = "/api/v1/internal/progress"


@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = DaprTransport(
        dapr_http_endpoint=settings.dapr_http_endpoint,
        routes={"inference-service": settings.inference_url, "api-gateway": settings.gateway_url},
        token=settings.internal_token,
    )
    async with httpx.AsyncClient() as client:
        app.state.http = client
        app.state.transport = transport
        yield


app = FastAPI(title="Buy You Before - Catalog Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "status": "ok",
        "skus": str(len(CATALOG)),
        "transport": "dapr" if settings.dapr_http_endpoint else "http",
    }


@app.get("/dapr/subscribe")
def dapr_subscriptions() -> list[dict[str, str]]:
    """daprd reads the topic but discards it unless the app confirms this list."""
    return [{"pubsubname": settings.pubsub_name, "topic": TOPIC_REQUESTED, "route": "/events"}]


@app.get("/api/v1/catalog")
def browse(limit: int = 200) -> list[dict[str, Any]]:
    """Read-only view used by the UI's example picker."""
    rows = []
    for item in CATALOG[: max(1, min(limit, len(CATALOG)))]:
        rows.append(
            {
                "sku": item.sku,
                "name": item.name,
                "brand": item.brand,
                "category": item.category,
                "material": item.material,
                "price_band": item.price_band,
                "geometry": item.geometry.model_dump(),
            }
        )
    return rows


def _unwrap(payload: Any) -> dict[str, Any]:
    """Dapr delivers a CloudEvent envelope; a direct call posts the bare message."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


async def _progress(request: Request, message: SimulationRequested) -> None:
    """Best-effort: the UI step bar should move even if the gateway is briefly unreachable."""
    try:
        response = await request.app.state.transport.request(
            request.app.state.http,
            "api-gateway",
            PROGRESS_METHOD,
            {"simulation_id": message.simulation_id, "status": SimulationStatus.cataloguing},
        )
        response.raise_for_status()
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.warning("simulation %s could not report progress: %s", message.simulation_id, exc)


async def _forward(request: Request, catalogued: SimulationCatalogued) -> None:
    payload = catalogued.model_dump()
    if await publish_event(request.app.state.http, settings.dapr_http_endpoint, settings.pubsub_name, TOPIC_CATALOGUED, payload):
        return
    response = await request.app.state.transport.request(request.app.state.http, "inference-service", "/v1/enrich", payload)
    response.raise_for_status()


async def catalogue(request: Request, message: SimulationRequested) -> SimulationCatalogued:
    candidate: CatalogCandidate | None = candidate_for(message.product_link or "", message.shopper_notes or "")
    logger.info(
        "simulation %s -> %s",
        message.simulation_id,
        f"{candidate.sku} ({candidate.score})" if candidate else "no catalog match",
    )
    return SimulationCatalogued(
        simulation_id=message.simulation_id,
        room_width_m=message.room_width_m,
        room_depth_m=message.room_depth_m,
        room_height_m=message.room_height_m,
        product_link=message.product_link,
        image_key=message.image_key,
        shopper_notes=message.shopper_notes,
        candidate=candidate,
    )


@app.post("/v1/catalogue")
async def catalogue_endpoint(payload: dict, request: Request) -> dict:
    message = SimulationRequested.model_validate(_unwrap(payload))
    catalogued = await catalogue(request, message)
    await _progress(request, message)
    await _forward(request, catalogued)
    return catalogued.model_dump()


@app.post("/events")
async def subscription(payload: dict, request: Request) -> dict[str, str]:
    """Dapr declarative subscription target for the `simulation.requested` topic."""
    message = SimulationRequested.model_validate(_unwrap(payload))
    catalogued = await catalogue(request, message)
    await _progress(request, message)
    await _forward(request, catalogued)
    return {"status": "SUCCESS"}


def start() -> None:
    import uvicorn

    uvicorn.run("byb_catalog.main:app", host="0.0.0.0", port=settings.port)


def dev() -> None:
    import uvicorn

    uvicorn.run("byb_catalog.main:app", host="0.0.0.0", port=settings.port, reload=True)


if __name__ == "__main__":
    start()
