"""Inference worker: reads the product listing, asks an AMD Token Factory
OpenAI-compatible model for real-world dimensions, then hands the measurement
to geometry-service."""

from __future__ import annotations

import base64
import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request

from byb_common.contracts import ProductProfile, SimulationMeasured, SimulationRequested
from byb_common.dapr import DaprTransport, publish_event
from byb_inference.products import extract_context, fallback_profile
from byb_inference.safe_fetch import FetchError, fetch_product_html
from byb_inference.settings import settings
from byb_inference.vllm_client import describe_product

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.inference")

TOPIC_MEASURED = "simulation.measured"


@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = DaprTransport(
        dapr_http_endpoint=settings.dapr_http_endpoint,
        routes={"geometry-service": settings.geometry_url},
        token=settings.internal_token,
    )
    async with httpx.AsyncClient(follow_redirects=True) as client:
        app.state.http = client
        app.state.transport = transport
        yield


app = FastAPI(title="Buy You Before - Inference Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "status": "ok",
        "model": settings.vllm_model or "unset",
        "llm_configured": "true" if settings.llm_configured else "false",
        "transport": "dapr" if settings.dapr_http_endpoint else "http",
    }


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


def _image_data_uri(image_key: str | None) -> str | None:
    if not (settings.vllm_supports_vision and image_key):
        return None
    path = Path(settings.upload_dir) / Path(image_key).name
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


async def enrich(message: SimulationRequested, client: httpx.AsyncClient) -> ProductProfile:
    context = await _page_context(client, message.product_link) if message.product_link else ""
    if message.shopper_notes:
        note_line = f"shopper notes: {message.shopper_notes.strip()}"
        context = f"{context}\n{note_line}".strip() if context else note_line

    profile = await describe_product(client, context, _image_data_uri(message.image_key))
    if profile is None:
        profile = fallback_profile(context, message.product_link)
    logger.info("simulation %s profiled as %r (%s)", message.simulation_id, profile.name, profile.source)
    return profile





async def _forward(request: Request, measured: SimulationMeasured) -> None:
    payload = measured.model_dump()
    if await publish_event(
        request.app.state.http, settings.dapr_http_endpoint, settings.pubsub_name, TOPIC_MEASURED, payload
    ):
        return
    response = await request.app.state.transport.request(request.app.state.http, "geometry-service", "/v1/measure", payload)
    response.raise_for_status()


def _unwrap(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


async def _measure_and_forward(request: Request, message: SimulationRequested) -> ProductProfile:
    profile = await enrich(message, request.app.state.http)
    await _forward(
        request,
        SimulationMeasured(
            simulation_id=message.simulation_id,
            profile=profile,
            room_width_m=message.room_width_m,
            room_depth_m=message.room_depth_m,
            room_height_m=message.room_height_m,
        ),
    )
    return profile


@app.post("/v1/profile")
async def profile_endpoint(payload: dict, request: Request) -> dict:
    """Enrich only (no geometry forward). Used to prove AMD vLLM wiring."""
    message = SimulationRequested.model_validate(_unwrap(payload))
    return (await enrich(message, request.app.state.http)).model_dump()


@app.post("/v1/enrich")
async def enrich_endpoint(payload: dict, request: Request) -> dict:
    message = SimulationRequested.model_validate(_unwrap(payload))
    return (await _measure_and_forward(request, message)).model_dump()


@app.post("/events")
async def subscription(payload: dict, request: Request) -> dict[str, str]:
    """Dapr declarative subscription target for the `simulation.requested` topic."""
    message = SimulationRequested.model_validate(_unwrap(payload))
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
