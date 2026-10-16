"""Geometry worker: consumes the scanned room, runs the Shapely fit analysis and
reports the outcome back to the gateway."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request

from byb_common.contracts import (
    FitReport,
    SimulationCompleted,
    SimulationProgress,
    SimulationRoomScanned,
    SimulationStatus,
)
from byb_common.dapr import DaprTransport
from byb_geometry.layout import analyse_fit
from byb_geometry.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.geometry")

RESULT_METHOD = "/api/v1/internal/results"
PROGRESS_METHOD = "/api/v1/internal/progress"
TOPIC_ROOM_SCANNED = "simulation.room_scanned"


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
    return [{"pubsubname": settings.pubsub_name, "topic": TOPIC_ROOM_SCANNED, "route": "/events"}]


async def _report(client: httpx.AsyncClient, transport: DaprTransport, completed: SimulationCompleted) -> None:
    try:
        response = await transport.request(client, "api-gateway", RESULT_METHOD, completed.model_dump())
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("could not report simulation %s: %s", completed.simulation_id, exc)


async def _progress(client: httpx.AsyncClient, transport: DaprTransport, simulation_id: str) -> None:
    """Best-effort: the step bar should move even if the gateway is briefly unreachable."""
    try:
        response = await transport.request(
            client,
            "api-gateway",
            PROGRESS_METHOD,
            SimulationProgress(simulation_id=simulation_id, status=SimulationStatus.fitting).model_dump(),
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("simulation %s could not report progress: %s", simulation_id, exc)


def _run_fit(message: SimulationRoomScanned) -> SimulationCompleted:
    if message.profile is None:
        return SimulationCompleted(
            simulation_id=message.simulation_id,
            status=SimulationStatus.failed,
            candidate=message.candidate,
            scan=message.scan,
            error="no product profile reached geometry-service",
        )
    fit: FitReport = analyse_fit(
        message.scan.width_m,
        message.scan.depth_m,
        message.scan.height_m,
        message.profile,
        wall_padding_m=settings.wall_padding_m,
        min_walkway_m=settings.min_walkway_m,
        obstacles=message.scan.obstacles,
    )
    logger.info(
        "simulation %s verdict=%s coverage=%.1f%% room=%sx%s m [%s]",
        message.simulation_id, fit.verdict, fit.coverage_pct, message.scan.width_m, message.scan.depth_m, message.scan.method,
    )
    return SimulationCompleted(
        simulation_id=message.simulation_id,
        status=SimulationStatus.completed,
        profile=message.profile,
        candidate=message.candidate,
        scan=message.scan,
        fit=fit,
    )


def _unwrap(payload: Any) -> dict[str, Any]:
    """Dapr delivers a CloudEvent envelope; a direct call posts the bare message."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


async def _process(request: Request, payload: dict) -> SimulationCompleted:
    message = SimulationRoomScanned.model_validate(_unwrap(payload))
    client, transport = request.app.state.http, request.app.state.transport
    await _progress(client, transport, message.simulation_id)
    completed = _run_fit(message)
    await _report(client, transport, completed)
    return completed


@app.post("/v1/fit", response_model=FitReport | None)
async def fit(payload: dict, request: Request) -> FitReport | None:
    completed = await _process(request, payload)
    return completed.fit


@app.post("/events")
async def subscription(payload: dict, request: Request) -> dict[str, str]:
    """Dapr declarative subscription target for the `simulation.room_scanned` topic."""
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
