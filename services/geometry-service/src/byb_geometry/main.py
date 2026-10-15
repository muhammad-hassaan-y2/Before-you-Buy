"""Geometry worker: consumes a measured product, runs the Shapely fit analysis and
reports the outcome back to the gateway."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request

from byb_common.contracts import FitReport, SimulationCompleted, SimulationMeasured, SimulationStatus
from byb_common.dapr import DaprTransport
from byb_geometry.layout import analyse_fit
from byb_geometry.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.geometry")

RESULT_METHOD = "/api/v1/internal/results"
TOPIC_MEASURED = "simulation.measured"


@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = DaprTransport(
        dapr_http_endpoint=settings.dapr_http_endpoint,
        routes={"api-gateway": settings.gateway_url},
        token=settings.internal_token,
    )
    async with httpx.AsyncClient() as client:
        app.state.http = client
        app.state.transport = transport
        yield


app = FastAPI(title="Buy You Before - Geometry Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"service": settings.service_name, "status": "ok", "transport": "dapr" if settings.dapr_http_endpoint else "http"}


@app.get("/dapr/subscribe")
def dapr_subscriptions() -> list[dict[str, str]]:
    """daprd reads the topic but discards it unless the app confirms this list."""
    return [{"pubsubname": settings.pubsub_name, "topic": TOPIC_MEASURED, "route": "/events"}]


async def _report(client: httpx.AsyncClient, transport: DaprTransport, completed: SimulationCompleted) -> None:
    try:
        response = await transport.request(client, "api-gateway", RESULT_METHOD, completed.model_dump())
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("could not report simulation %s: %s", completed.simulation_id, exc)


def _run_measurement(message: SimulationMeasured) -> SimulationCompleted:
    if message.profile is None:
        return SimulationCompleted(
            simulation_id=message.simulation_id,
            status=SimulationStatus.failed,
            candidate=message.candidate,
            error="no product profile reached geometry-service",
        )
    fit: FitReport = analyse_fit(
        message.room_width_m,
        message.room_depth_m,
        message.room_height_m,
        message.profile,
        wall_padding_m=settings.wall_padding_m,
        min_walkway_m=settings.min_walkway_m,
    )
    logger.info("simulation %s verdict=%s coverage=%.1f%%", message.simulation_id, fit.verdict, fit.coverage_pct)
    return SimulationCompleted(
        simulation_id=message.simulation_id,
        status=SimulationStatus.completed,
        profile=message.profile,
        candidate=message.candidate,
        fit=fit,
    )


def _unwrap(payload: Any) -> dict[str, Any]:
    """Dapr delivers a CloudEvent envelope; a direct call posts the bare message."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


async def _process(request: Request, payload: dict) -> SimulationCompleted:
    message = SimulationMeasured.model_validate(_unwrap(payload))
    client, transport = request.app.state.http, request.app.state.transport
    if message.profile is not None:
        await _report(
            client,
            transport,
            SimulationCompleted(simulation_id=message.simulation_id, status=SimulationStatus.measuring),
        )
    completed = _run_measurement(message)
    await _report(client, transport, completed)
    return completed


@app.post("/v1/measure", response_model=FitReport | None)
async def measure(payload: dict, request: Request) -> FitReport | None:
    completed = await _process(request, payload)
    return completed.fit


@app.post("/events")
async def subscription(payload: dict, request: Request) -> dict[str, str]:
    """Dapr declarative subscription target for the `simulation.measured` topic."""
    await _process(request, payload)
    return {"status": "SUCCESS"}


def start() -> None:
    import uvicorn

    uvicorn.run("byb_geometry.main:app", host="0.0.0.0", port=settings.port)


def dev() -> None:
    import uvicorn

    uvicorn.run("byb_geometry.main:app", host="0.0.0.0", port=settings.port, reload=True)


if __name__ == "__main__":
    start()
