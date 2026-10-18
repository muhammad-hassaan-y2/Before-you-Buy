"""Vision worker: reads the room photo, measures it, and passes the product profile on
to geometry-service with the room the fit analysis should use."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request

from byb_common.contracts import RoomScan, SimulationMeasured, SimulationRoomScanned, SimulationStatus
from byb_common.dapr import DaprTransport, publish_event
from byb_vision.photo import scan_photo
from byb_vision.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.vision")

TOPIC_MEASURED = "simulation.measured"
TOPIC_ROOM_SCANNED = "simulation.room_scanned"
PROGRESS_METHOD = "/api/v1/internal/progress"


@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = DaprTransport(
        dapr_http_endpoint=settings.dapr_http_endpoint,
        routes={"geometry-service": settings.geometry_url, "api-gateway": settings.gateway_url},
        token=settings.internal_token,
    )
    async with httpx.AsyncClient() as client:
        app.state.http = client
        app.state.transport = transport
        yield


app = FastAPI(title="Before You Buy - Vision Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "status": "ok",
        "uploads": str(Path(settings.upload_dir).is_dir()),
        "transport": "dapr" if settings.dapr_http_endpoint else "http",
    }


@app.get("/dapr/subscribe")
def dapr_subscriptions() -> list[dict[str, str]]:
    """daprd reads the topic but discards it unless the app confirms this list."""
    return [{"pubsubname": settings.pubsub_name, "topic": TOPIC_MEASURED, "route": "/events"}]


def _unwrap(payload: Any) -> dict[str, Any]:
    """Dapr delivers a CloudEvent envelope; a direct call posts the bare message."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def declared_scan(message: SimulationMeasured) -> RoomScan:
    return RoomScan(
        width_m=message.room_width_m,
        depth_m=message.room_depth_m,
        height_m=message.room_height_m,
        measured=False,
        method="declared",
    )


def measure_room(message: SimulationMeasured) -> RoomScan:
    """No photo, or an unreadable one, is a normal outcome: the declared room stands."""
    if not message.image_key:
        return declared_scan(message)
    path = Path(settings.upload_dir) / Path(message.image_key).name
    if not path.is_file():
        logger.warning("simulation %s references a missing upload: %s", message.simulation_id, path)
        return declared_scan(message)
    scan = scan_photo(
        path,
        room_width_m=message.room_width_m,
        room_depth_m=message.room_depth_m,
        room_height_m=message.room_height_m,
        min_confidence=settings.min_confidence,
        max_obstacles=settings.max_obstacles,
    )
    logger.info(
        "simulation %s room %sx%s m (%s, %.2f)",
        message.simulation_id, scan.width_m, scan.depth_m, scan.method, scan.confidence,
    )
    return scan


async def _progress(request: Request, simulation_id: str) -> None:
    """Best-effort: the step bar should move even if the gateway is briefly unreachable."""
    try:
        response = await request.app.state.transport.request(
            request.app.state.http, "api-gateway", PROGRESS_METHOD,
            {"simulation_id": simulation_id, "status": SimulationStatus.scanning},
        )
        response.raise_for_status()
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.warning("simulation %s could not report progress: %s", simulation_id, exc)


async def _forward(request: Request, scanned: SimulationRoomScanned) -> None:
    payload = scanned.model_dump()
    if await publish_event(
        request.app.state.http, settings.dapr_http_endpoint, settings.pubsub_name, TOPIC_ROOM_SCANNED, payload
    ):
        return
    response = await request.app.state.transport.request(request.app.state.http, "geometry-service", "/v1/fit", payload)
    response.raise_for_status()


async def _scan_and_forward(request: Request, message: SimulationMeasured) -> SimulationRoomScanned:
    await _progress(request, message.simulation_id)
    scanned = SimulationRoomScanned(
        simulation_id=message.simulation_id,
        profile=message.profile,
        candidate=message.candidate,
        scan=measure_room(message),
    )
    await _forward(request, scanned)
    return scanned


@app.post("/v1/scan")
async def scan_endpoint(payload: dict, request: Request) -> dict:
    message = SimulationMeasured.model_validate(_unwrap(payload))
    return (await _scan_and_forward(request, message)).scan.model_dump()


@app.post("/events")
async def subscription(payload: dict, request: Request) -> dict[str, str]:
    """Dapr declarative subscription target for the `simulation.measured` topic."""
    message = SimulationMeasured.model_validate(_unwrap(payload))
    await _scan_and_forward(request, message)
    return {"status": "SUCCESS"}


def start() -> None:
    import uvicorn

    uvicorn.run("byb_vision.main:app", host="0.0.0.0", port=settings.port)


def dev() -> None:
    import uvicorn

    uvicorn.run("byb_vision.main:app", host="0.0.0.0", port=settings.port, reload=True)


if __name__ == "__main__":
    start()
