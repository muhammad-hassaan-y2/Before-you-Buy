"""Geometry worker: consumes the scanned room, runs the Shapely fit analysis and hands the
result to scene-service, which is the worker that finishes the simulation.

A simulation with no product profile dies here, so this is the one case where geometry
reports straight to the gateway instead of passing the message on.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request

from byb_common.contracts import (
    FitReport,
    SimulationCompleted,
    SimulationFitted,
    SimulationProgress,
    SimulationRoomScanned,
    SimulationStatus,
)
from byb_common.dapr import DaprTransport, publish_event
from byb_geometry.access import check_access
from byb_geometry.layout import analyse_fit
from byb_geometry.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.geometry")

RESULT_METHOD = "/api/v1/internal/results"
PROGRESS_METHOD = "/api/v1/internal/progress"
TOPIC_ROOM_SCANNED = "simulation.room_scanned"
TOPIC_FITTED = "simulation.fitted"


@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = DaprTransport(
        dapr_http_endpoint=settings.dapr_http_endpoint,
        routes={"scene-service": settings.scene_url, "api-gateway": settings.gateway_url},
        token=settings.internal_token,
    )
    async with httpx.AsyncClient() as client:
        app.state.http = client
        app.state.transport = transport
        yield


app = FastAPI(title="Before You Buy - Geometry Service", version="0.1.0", lifespan=lifespan)


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


async def _forward(client: httpx.AsyncClient, transport: DaprTransport, fitted: SimulationFitted) -> None:
    payload = fitted.model_dump()
    if await publish_event(client, settings.dapr_http_endpoint, settings.pubsub_name, TOPIC_FITTED, payload):
        return
    response = await transport.request(client, "scene-service", "/v1/render", payload)
    response.raise_for_status()


def _run_fit(message: SimulationRoomScanned) -> FitReport:
    fit: FitReport = analyse_fit(
        message.scan.width_m,
        message.scan.depth_m,
        message.scan.height_m,
        message.profile,
        wall_padding_m=settings.wall_padding_m,
        min_walkway_m=settings.min_walkway_m,
        obstacles=message.scan.obstacles,
    )
    fit = _with_access(fit, message)
    logger.info(
        "simulation %s verdict=%s coverage=%.1f%% room=%sx%s m [%s]",
        message.simulation_id, fit.verdict, fit.coverage_pct, message.scan.width_m, message.scan.depth_m, message.scan.method,
    )
    return fit


def _with_access(fit: FitReport, message: SimulationRoomScanned) -> FitReport:
    """Fold the delivery path - doorway, walkway, measurement margin - into the report.

    A box that cannot be carried in is not a fit, whatever the floor area says, so that one
    outcome is allowed to override the verdict. The rest is reported beside it and the agent
    decides how much weight to give it.
    """
    scan, profile = message.scan, message.profile
    access = check_access(
        scan,
        profile,
        fit.placements,
        wall_padding_m=settings.wall_padding_m,
        min_walkway_m=settings.min_walkway_m,
        tolerance_cm=settings.tolerance_cm,
    )

    conflicts = list(fit.conflicts)
    verdict = fit.verdict
    if access.door_pass == "blocked":
        conflicts.append(
            f"{profile.name} cannot pass the {scan.door_width_m * 100:.0f} cm by "
            f"{scan.door_height_m * 100:.0f} cm doorway, even tilted."
        )
        verdict = "blocked"
    elif access.door_pass == "tight":
        conflicts.append(
            f"{profile.name} only clears the doorway by the measurement margin (+/{access.tolerance_cm:g} cm) - re-measure the opening."
        )
    if not access.walkway_connected:
        conflicts.append(
            f"With it placed here there is less than {profile.geometry.clearance_cm / 100:.2f} m to walk from the door."
        )
    if access.isolated_pockets:
        conflicts.append(f"It cuts {access.isolated_pockets} area(s) of the room off from the door.")
    if access.fragile and verdict == "fits":
        conflicts.append(f"It fits on the stated numbers, but a {access.tolerance_cm:g} cm measurement error breaks it.")

    return fit.model_copy(
        update={
            "verdict": verdict,
            "conflicts": conflicts,
            "door_pass": access.door_pass,
            "walkway_connected": access.walkway_connected,
            "isolated_pockets": access.isolated_pockets,
            "fragile": access.fragile,
            "tolerance_cm": access.tolerance_cm,
            "suggestions": access.suggestions,
        }
    )


def _unwrap(payload: Any) -> dict[str, Any]:
    """Dapr delivers a CloudEvent envelope; a direct call posts the bare message."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


async def _process(request: Request, payload: dict) -> FitReport | None:
    message = SimulationRoomScanned.model_validate(_unwrap(payload))
    client, transport = request.app.state.http, request.app.state.transport
    await _progress(client, transport, message.simulation_id)

    if message.profile is None:
        await _report(
            client,
            transport,
            SimulationCompleted(
                simulation_id=message.simulation_id,
                status=SimulationStatus.failed,
                candidate=message.candidate,
                scan=message.scan,
                error="no product profile reached geometry-service",
            ),
        )
        return None

    fit = _run_fit(message)
    await _forward(
        client,
        transport,
        SimulationFitted(
            simulation_id=message.simulation_id,
            profile=message.profile,
            candidate=message.candidate,
            scan=message.scan,
            fit=fit,
        ),
    )
    return fit


@app.post("/v1/fit", response_model=FitReport | None)
async def fit(payload: dict, request: Request) -> FitReport | None:
    return await _process(request, payload)


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
