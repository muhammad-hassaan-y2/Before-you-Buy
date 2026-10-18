"""Inference worker: takes the catalog candidate (if any), reads the listing, asks an
AMD Token Factory OpenAI-compatible model for real-world dimensions, then hands the
measurement on to vision-service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request

from byb_common.contracts import (
    ProductProfile,
    SimulationCatalogued,
    SimulationMeasured,
    SimulationStatus,
)
from byb_common.dapr import DaprTransport, publish_event
from byb_inference.products import best_profile, extract_context, fallback_profile, profile_from_candidate
from byb_inference.safe_fetch import FetchError, fetch_product_html
from byb_inference.settings import settings
from byb_inference.vllm_client import describe_product

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.inference")

TOPIC_CATALOGUED = "simulation.catalogued"
TOPIC_MEASURED = "simulation.measured"
PROGRESS_METHOD = "/api/v1/internal/progress"


@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = DaprTransport(
        dapr_http_endpoint=settings.dapr_http_endpoint,
        routes={"vision-service": settings.vision_url, "api-gateway": settings.gateway_url},
        token=settings.internal_token,
    )
    async with httpx.AsyncClient(follow_redirects=True) as client:
        app.state.http = client
        app.state.transport = transport
        yield


app = FastAPI(title="Before You Buy - Inference Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "status": "ok",
        "model": settings.vllm_model or "unset",
        "llm_configured": "true" if settings.llm_configured else "false",
        "transport": "dapr" if settings.dapr_http_endpoint else "http",
    }


@app.get("/dapr/subscribe")
def dapr_subscriptions() -> list[dict[str, str]]:
    """daprd reads the topic but discards it unless the app confirms this list."""
    return [{"pubsubname": settings.pubsub_name, "topic": TOPIC_CATALOGUED, "route": "/events"}]


async def _page_context(client: httpx.AsyncClient, link: str) -> str:
    try:
        html_body = await fetch_product_html(
            client,
            link,
            timeout_s=settings.scrape_timeout_s,
            user_agent=settings.user_agent,
        )
    except FetchError as exc:
        logger.warning("could not safely read %s: %s", link, exc)
        return ""
    return extract_context(html_body)


async def enrich(message: SimulationCatalogued, client: httpx.AsyncClient) -> ProductProfile:
    context = await _page_context(client, message.product_link) if message.product_link else ""
    if message.shopper_notes:
        note_line = f"shopper notes: {message.shopper_notes.strip()}"
        context = f"{context}\n{note_line}".strip() if context else note_line

    # message.image_key is the shopper's *room* photo, which vision-service measures. The listing
    # page is the only source of a product picture, so the model is never shown it as product evidence.
    token_factory = await describe_product(client, context)
    from_catalog = profile_from_candidate(message.candidate) if message.candidate else None
    profile = best_profile(from_catalog, token_factory) or fallback_profile(context, message.product_link)

    # The engine always needs boxes, even when the winner came from Token Factory.
    if not profile.parts and message.candidate:
        profile = profile.model_copy(
            update={
                "parts": profile_from_candidate(message.candidate).parts,
                "category": profile.category or message.candidate.category,
            }
        )
    logger.info("simulation %s profiled as %r (%s)", message.simulation_id, profile.name, profile.source)
    return profile


async def _progress(request: Request, simulation_id: str, status: SimulationStatus) -> None:
    """Best-effort stage report so the browser can follow the chain."""
    try:
        response = await request.app.state.transport.request(
            request.app.state.http, "api-gateway", PROGRESS_METHOD, {"simulation_id": simulation_id, "status": status}
        )
        response.raise_for_status()
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.warning("simulation %s could not report %s: %s", simulation_id, status, exc)


async def _forward(request: Request, measured: SimulationMeasured) -> None:
    payload = measured.model_dump()
    if await publish_event(
        request.app.state.http, settings.dapr_http_endpoint, settings.pubsub_name, TOPIC_MEASURED, payload
    ):
        return
    response = await request.app.state.transport.request(request.app.state.http, "vision-service", "/v1/scan", payload)
    response.raise_for_status()


def _unwrap(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


async def _measure_and_forward(request: Request, message: SimulationCatalogued) -> ProductProfile:
    await _progress(request, message.simulation_id, SimulationStatus.enriching)
    profile = await enrich(message, request.app.state.http)
    await _forward(
        request,
        SimulationMeasured(
            simulation_id=message.simulation_id,
            profile=profile,
            candidate=message.candidate,
            room_width_m=message.room_width_m,
            room_depth_m=message.room_depth_m,
            room_height_m=message.room_height_m,
            image_key=message.image_key,
        ),
    )
    return profile


@app.post("/v1/profile")
async def profile_endpoint(payload: dict, request: Request) -> dict:
    """Enrich only (no vision forward). Used to prove AMD Token Factory wiring."""
    message = SimulationCatalogued.model_validate(_unwrap(payload))
    return (await enrich(message, request.app.state.http)).model_dump()


@app.post("/v1/enrich")
async def enrich_endpoint(payload: dict, request: Request) -> dict:
    message = SimulationCatalogued.model_validate(_unwrap(payload))
    return (await _measure_and_forward(request, message)).model_dump()


@app.post("/events")
async def subscription(payload: dict, request: Request) -> dict[str, str]:
    """Dapr declarative subscription target for the `simulation.catalogued` topic."""
    message = SimulationCatalogued.model_validate(_unwrap(payload))
    await _measure_and_forward(request, message)
    return {"status": "SUCCESS"}


def start() -> None:
    import uvicorn

    uvicorn.run("byb_inference.main:app", host="0.0.0.0", port=settings.port)


def dev() -> None:
    import uvicorn

    uvicorn.run("byb_inference.main:app", host="0.0.0.0", port=settings.port, reload=True)


if __name__ == "__main__":
    start()
