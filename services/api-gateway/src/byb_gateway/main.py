"""Buy You Before API gateway: accepts a room image or product link, persists the job
and publishes it to the head of the worker chain."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from byb_common.contracts import SimulationCompleted, SimulationProgress, SimulationRequested, SimulationStatus
from byb_common.dapr import INTERNAL_TOKEN_HEADER, DaprTransport
from byb_gateway.database import get_db, init_db
from byb_gateway.dispatch import Dispatcher
from byb_gateway.models import Simulation, SimulationResult
from byb_gateway.schemas import HealthResponse, SimulationAccepted, SimulationDetail, SimulationSummary
from byb_gateway.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.gateway")

MAX_CHUNK = 1024 * 512


@asynccontextmanager
async def lifespan(app: FastAPI):
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    init_db()
    transport = DaprTransport(
        dapr_http_endpoint=settings.dapr_http_endpoint,
        routes={"catalog-service": settings.catalog_url},
        token=settings.internal_token,
    )
    async with httpx.AsyncClient() as client:
        app.state.http = client
        app.state.transport = transport
        app.state.dispatch = Dispatcher(client, transport)
        yield


app = FastAPI(title="Buy You Before - API Gateway", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", INTERNAL_TOKEN_HEADER],
)


def require_internal_token(x_byb_token: str = Header(default="")) -> None:
    if x_byb_token != settings.internal_token:
        raise HTTPException(status_code=403, detail="Invalid internal token")


@app.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        init_db()
        database = "up"
    except Exception as exc:  # noqa: BLE001 - health must report, not raise
        logger.warning("database unreachable: %s", exc)
        database = "down"
    return HealthResponse(
        service=settings.service_name,
        status="ok",
        database=database,
        dapr="sidecar" if settings.dapr_http_endpoint else "direct",
        transport="dapr" if settings.dapr_http_endpoint else "http",
    )


def _save_upload(file: UploadFile, simulation_id: str) -> str:
    safe_name = Path(file.filename or "room.png").name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Unsafe file name")
    key = f"{simulation_id}-{safe_name}"
    destination = Path(settings.upload_dir) / key
    limit = settings.max_upload_mb * 1024 * 1024
    written = 0
    with destination.open("wb") as handle:
        while chunk := file.file.read(MAX_CHUNK):
            written += len(chunk)
            if written > limit:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Image exceeds {settings.max_upload_mb} MB limit")
            handle.write(chunk)
    return key


@app.post("/api/v1/simulations", response_model=SimulationAccepted, status_code=202)
async def create_simulation(
    link: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    room_width_m: float = Form(default=4.0),
    room_depth_m: float = Form(default=3.5),
    room_height_m: float = Form(default=2.4),
    shopper_notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> SimulationAccepted:
    if not link and not file:
        raise HTTPException(status_code=400, detail="Provide a product link or a room image")
    if not 0.5 <= room_width_m <= 50 or not 0.5 <= room_depth_m <= 50 or not 1.2 <= room_height_m <= 12:
        raise HTTPException(status_code=422, detail="Room dimensions are out of range")

    simulation = Simulation(
        product_link=link,
        room_width_m=room_width_m,
        room_depth_m=room_depth_m,
        room_height_m=room_height_m,
        shopper_notes=shopper_notes,
        status=SimulationStatus.pending,
    )
    db.add(simulation)
    db.commit()
    db.refresh(simulation)

    image_key = None
    if file and file.filename:
        try:
            image_key = _save_upload(file, simulation.id)
            simulation.image_key = image_key
            db.commit()
        except HTTPException:
            raise
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Could not store upload: {exc}") from exc

    message = SimulationRequested(
        simulation_id=simulation.id,
        room_width_m=room_width_m,
        room_depth_m=room_depth_m,
        room_height_m=room_height_m,
        product_link=link,
        image_key=image_key,
        shopper_notes=shopper_notes,
    )
    # Mark before fanning out: on the direct-HTTP path this await runs the whole
    # worker chain, and a fast worker's callback would otherwise be reverted here.
    simulation.status = SimulationStatus.cataloguing
    db.commit()
    try:
        await app.state.dispatch.start(message)
    except (httpx.HTTPError, RuntimeError) as exc:
        simulation.status = SimulationStatus.failed
        simulation.error = f"worker unavailable: {exc}"
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SimulationAccepted(id=simulation.id, status=simulation.status)


@app.get("/api/v1/simulations/{simulation_id}", response_model=SimulationDetail)
def get_simulation(simulation_id: str, db: Session = Depends(get_db)) -> SimulationDetail:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    result = simulation.result
    return SimulationDetail(
        id=simulation.id,
        status=simulation.status,
        product_link=simulation.product_link,
        image_key=simulation.image_key,
        created_at=simulation.created_at,
        error=simulation.error,
        room_width_m=simulation.room_width_m,
        room_depth_m=simulation.room_depth_m,
        room_height_m=simulation.room_height_m,
        shopper_notes=simulation.shopper_notes,
        updated_at=simulation.updated_at,
        product_profile=result.product_profile if result else None,
        catalog_candidate=result.catalog_candidate if result else None,
        room_scan=result.room_scan if result else None,
        fit_report=result.fit_report if result else None,
    )


@app.get("/api/v1/simulations", response_model=list[SimulationSummary])
def list_simulations(limit: int = 20, db: Session = Depends(get_db)) -> list[SimulationSummary]:
    rows = db.scalars(select(Simulation).order_by(Simulation.created_at.desc()).limit(min(limit, 100)))
    return [SimulationSummary.model_validate(row) for row in rows]


def _elapsed_ms(created_at: datetime) -> int:
    # SQLite hands back naive datetimes while Postgres returns aware ones.
    started = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    return int((datetime.now(UTC) - started).total_seconds() * 1000)


@app.post("/api/v1/internal/results", status_code=204, dependencies=[Depends(require_internal_token)])
def record_result(completed: SimulationCompleted, db: Session = Depends(get_db)) -> None:
    simulation = db.get(Simulation, completed.simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Unknown simulation")

    simulation.status = completed.status
    simulation.error = completed.error
    simulation.attempts += 1
    if completed.profile or completed.fit:
        result = simulation.result or SimulationResult(simulation_id=simulation.id)
        result.product_profile = completed.profile.model_dump() if completed.profile else None
        result.catalog_candidate = completed.candidate.model_dump() if completed.candidate else None
        if completed.scan:
            # Only geometry reports a scan, so a stage callback must not blank it out.
            result.room_scan = completed.scan.model_dump()
        result.fit_report = completed.fit.model_dump() if completed.fit else None
        result.duration_ms = _elapsed_ms(simulation.created_at)
        db.add(result)
    db.commit()
    logger.info("simulation %s -> %s", simulation.id, completed.status)


@app.post("/api/v1/internal/progress", status_code=204, dependencies=[Depends(require_internal_token)])
def record_progress(progress: SimulationProgress, db: Session = Depends(get_db)) -> None:
    """A worker announcing the stage it reached. Never moves a settled simulation."""
    simulation = db.get(Simulation, progress.simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Unknown simulation")
    if simulation.status in {SimulationStatus.completed, SimulationStatus.failed}:
        return
    simulation.status = progress.status
    db.commit()
    logger.info("simulation %s reached %s", simulation.id, progress.status)


@app.get("/api/v1/catalog")
async def catalog_examples(request: Request) -> list[dict]:
    """Read-only catalog passthrough so the browser never learns a second origin."""
    transport: DaprTransport = request.app.state.transport
    try:
        response = await request.app.state.http.get(
            transport.url("catalog-service", "/api/v1/catalog"), headers=transport.headers(), timeout=10
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("catalog-service unreachable: %s", exc)
        raise HTTPException(status_code=502, detail="catalog-service unavailable") from exc
    return response.json()


def start() -> None:
    """`poetry run start` - production entrypoint used by the Docker image."""
    import uvicorn

    uvicorn.run("byb_gateway.main:app", host="0.0.0.0", port=settings.port)


def dev() -> None:
    """`poetry run dev` - reload loop for local development."""
    import uvicorn

    uvicorn.run("byb_gateway.main:app", host="0.0.0.0", port=settings.port, reload=True)


if __name__ == "__main__":
    start()
