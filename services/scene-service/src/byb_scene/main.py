"""Scene worker: last hop in the chain. Builds the SceneSpec and a glTF 2.0 document from the
fit report, then reports the finished simulation to the gateway."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request

from byb_common.contracts import SceneSpec, SimulationCompleted, SimulationFitted, SimulationProgress, SimulationStatus
from byb_common.dapr import DaprTransport
from byb_scene.gltf import build_gltf
from byb_scene.settings import settings
from byb_scene.spec import SceneInputError, best_placement, build_scene

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.scene")

RESULT_METHOD = "/api/v1/internal/results"
PROGRESS_METHOD = "/api/v1/internal/progress"
TOPIC_FITTED = "simulation.fitted"


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


app = FastAPI(title="Buy You Before - Scene Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"service": settings.service_name, "status": "ok", "transport": "dapr" if settings.dapr_http_endpoint else "http"}


@app.get("/dapr/subscribe")
def dapr_subscriptions() -> list[dict[str, str]]:
    """daprd reads the topic but discards it unless the app confirms this list."""
    return [{"pubsubname": settings.pubsub_name, "topic": TOPIC_FITTED, "route": "/events"}]


def _unwrap(payload: Any) -> dict[str, Any]:
    """Dapr delivers a CloudEvent envelope; a direct call posts the bare message."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def render(fitted: SimulationFitted) -> tuple[SceneSpec, dict[str, Any]]:
    scene = build_scene(fitted, max_parts=settings.max_parts)
    return scene, build_gltf(scene, best_placement(scene.placements))


async def _progress(request: Request, simulation_id: str) -> None:
    """Best-effort: the step bar should move even if the gateway is briefly unreachable."""
    try:
        response = await request.app.state.transport.request(
            request.app.state.http,
            "api-gateway",
            PROGRESS_METHOD,
            SimulationProgress(simulation_id=simulation_id, status=SimulationStatus.rendering).model_dump(),
        )
        response.raise_for_status()
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.warning("simulation %s could not report progress: %s", simulation_id, exc)


async def _report(request: Request, completed: SimulationCompleted) -> None:
    response = await request.app.state.transport.request(request.app.state.http, "api-gateway", RESULT_METHOD, completed.model_dump())
    response.raise_for_status()


async def _render_and_report(request: Request, fitted: SimulationFitted) -> SimulationCompleted:
    """Whatever happens, the gateway gets a final answer: a scene or an error it can show."""
    await _progress(request, fitted.simulation_id)
    try:
        scene, gltf = render(fitted)
    except SceneInputError as exc:
        logger.error("simulation %s cannot be rendered: %s", fitted.simulation_id, exc)
        completed = SimulationCompleted(
            simulation_id=fitted.simulation_id,
            status=SimulationStatus.failed,
            profile=fitted.profile,
            candidate=fitted.candidate,
            scan=fitted.scan,
            fit=fitted.fit,
            error=str(exc),
        )
    else:
        logger.info(
            "simulation %s scene: %d parts, %d placements, %d nodes in the model",
            fitted.simulation_id, len(scene.parts), len(scene.placements), len(gltf["nodes"]),
        )
        completed = SimulationCompleted(
            simulation_id=fitted.simulation_id,
            status=SimulationStatus.completed,
            profile=fitted.profile,
            candidate=fitted.candidate,
            scan=fitted.scan,
            fit=fitted.fit,
            scene=scene,
            gltf=gltf,
        )
    try:
        await _report(request, completed)
    except httpx.HTTPError as exc:
        logger.error("could not report simulation %s: %s", fitted.simulation_id, exc)
    return completed


@app.post("/v1/render")
async def render_endpoint(payload: dict, request: Request) -> dict[str, Any]:
    completed = await _render_and_report(request, SimulationFitted.model_validate(_unwrap(payload)))
    if completed.scene:
        return completed.scene.model_dump()
    return {"simulation_id": completed.simulation_id, "status": completed.status, "error": completed.error}


@app.post("/events")
async def subscription(payload: dict, request: Request) -> dict[str, str]:
    """Dapr declarative subscription target for the `simulation.fitted` topic."""
    await _render_and_report(request, SimulationFitted.model_validate(_unwrap(payload)))
    return {"status": "SUCCESS"}


def start() -> None:
    import uvicorn

    uvicorn.run("byb_scene.main:app", host="0.0.0.0", port=settings.port)


def dev() -> None:
    import uvicorn

    uvicorn.run("byb_scene.main:app", host="0.0.0.0", port=settings.port, reload=True)


if __name__ == "__main__":
    start()
