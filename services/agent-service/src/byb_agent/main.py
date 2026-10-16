"""Agent service: the surface an Evolus agent works through.

One set of capabilities, reachable through several doors:

* `/agent/tools` and `/agent/tools/{name}` - REST, for an Evolus workflow step or a webhook.
* `/mcp/` - the MCP connector, for the agent itself.
* `/agent/brief`, `/agent/runs`, `/agent/chat` - the shop's own UI.
* `/agent/reservations` - the holds a human agreed to, waiting on a person at the shop.

Everything upstream is configured by environment: the Evolus workspace, the open model served
on AMD, and the six-service pipeline. Absent credentials degrade, they do not stall.
"""

from __future__ import annotations

import inspect
import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from byb_agent.contracts import BriefRequest
from byb_agent.evolus import Evolus, EvolusError
from byb_agent.mcp_server import build_server, http_app
from byb_agent.model import AMDModel
from byb_agent.pipeline import Pipeline
from byb_agent.runs import Reservations, RunStore
from byb_agent.settings import settings
from byb_agent.tools import SPEC, Tools

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.agent")

INTERNAL_TOKEN_HEADER = "x-byb-token"

# Built once, at import, so the MCP app can be mounted before the first request arrives.
HTTP = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0))
STORE = RunStore()
RESERVATIONS = Reservations()
PIPELINE = Pipeline(HTTP, settings)
EVOLUS = Evolus(HTTP, settings)
MODEL = AMDModel(HTTP, settings)
TOOLS = Tools(PIPELINE, EVOLUS, MODEL, STORE, settings, RESERVATIONS)
MCP_SERVER = build_server(TOOLS)
MCP_APP = http_app(MCP_SERVER, settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # A mounted ASGI app is not given a lifespan of its own; the MCP session manager runs here.
    async with MCP_APP.router.lifespan_context(MCP_APP), HTTP:
        logger.info("agent service up: evolus=%s model=%s", "yes" if EVOLUS.credentials else "no", MODEL.name or "heuristic")
        yield


app = FastAPI(title="Buy You Before - Agent Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", INTERNAL_TOKEN_HEADER, "X-Conversation-Id"],
)
app.mount("/mcp", MCP_APP)


@app.get("/healthz")
def health() -> dict[str, Any]:
    return {
        "service": settings.service_name,
        "status": "ok",
        "evolus": "connected" if EVOLUS.credentials else "not configured",
        "agent": settings.evolus_agent_id or "-",
        "model": MODEL.name or "heuristic",
        "workflow": settings.evolus_workflow_id or "-",
        "library": settings.evolus_library_id or "-",
        "mcp": "/mcp",
        "runs": str(len(STORE)),
        "tools": str(len(SPEC)),
        "reservations": str(len(RESERVATIONS)),
    }


@app.get("/agent/tools")
def tools_catalog() -> dict[str, Any]:
    """What the agent can do, in the shape an Evolus AI Tool list wants."""
    return {"tools": [{"name": name, "description": description} for name, description in SPEC.items()]}


@app.post("/agent/tools/{name}")
async def call_tool(name: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Invoke one capability with a JSON body - the endpoint Evolus calls."""
    if name not in SPEC:
        raise HTTPException(status_code=404, detail=f"unknown tool {name!r}")
    method = getattr(TOOLS, name)
    allowed = set(inspect.signature(method).parameters)
    try:
        result = await method(**{key: value for key, value in payload.items() if key in allowed})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"pipeline unavailable: {exc}") from exc
    return {"tool": name, "result": _jsonable(result)}


@app.post("/agent/brief", status_code=202)
async def start_brief(brief: BriefRequest) -> dict[str, Any]:
    """Start a fit-assurance journey from a shopper's words."""
    return await TOOLS.start_journey(brief.brief, brief.room_width_m, brief.room_depth_m, brief.room_height_m)


@app.get("/agent/runs")
def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    return [run.model_dump(include={"id", "status", "evolus_execution_id"}) for run in STORE.recent(limit)]


@app.get("/agent/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = STORE.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run")
    return run.model_dump()


@app.get("/agent/reservations")
def list_reservations(limit: int = 20) -> list[dict[str, Any]]:
    """Holds the agent took on a shopper's own yes, newest first, waiting on a person."""
    return TOOLS.list_reservations(limit)


@app.post("/agent/webhooks/evolus", status_code=202)
async def evolus_webhook(request: Request, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Where an Evolus workflow puts its result.

    The run id rides in the query string, because a workflow's webhook URL is configured once
    and not per run; `X-Workflow-Execution-Id` ties each delivery to the execution that made it.
    """
    run_id = request.query_params.get("run")
    run = STORE.get(run_id) if run_id else None
    if run is None:
        logger.info("evolus webhook for unknown run %s: %s", run_id or "-", str(payload)[:200])
        return {"received": True, "attached": False}
    run.callback = payload
    run.evolus_execution_id = run.evolus_execution_id or request.headers.get("x-workflow-execution-id")
    logger.info("run %s received a workflow result (%d keys)", run.id, len(payload))
    return {"received": True, "attached": True, "run_id": run.id}


@app.post("/agent/chat")
async def chat(request: Request, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Talk to the Evolus agent. The browser never learns the Evolus key.

    With no agent id configured the team's own AMD-hosted model answers instead, and the reply
    says which of the two spoke - the UI must not imply Evolus took part when it did not.
    """
    messages = payload.get("messages") or []
    if not messages:
        raise HTTPException(status_code=422, detail="messages are required")
    prompt = str(messages[-1].get("content", ""))
    conversation = payload.get("conversation_id") or request.headers.get("x-conversation-id")
    try:
        answer, conversation_id = await EVOLUS.ask(prompt, conversation_id=conversation)
        return {"answer": answer, "answered_by": "evolus", "conversation_id": conversation_id}
    except EvolusError as exc:
        logger.info("evolus chat unavailable, using the AMD-hosted model: %s", exc)
    if not MODEL.configured:
        raise HTTPException(status_code=503, detail="neither Evolus nor an AMD model endpoint is configured")
    try:
        answer = await MODEL.complete(prompt, system="You are the Buy You Before fit assistant. Be brief and concrete.", max_tokens=400)
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=f"AMD model endpoint failed: {exc}") from exc
    return {"answer": answer, "answered_by": MODEL.name}


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def start() -> None:
    import uvicorn

    uvicorn.run("byb_agent.main:app", host="0.0.0.0", port=settings.port)


def dev() -> None:
    import uvicorn

    uvicorn.run("byb_agent.main:app", host="0.0.0.0", port=settings.port, reload=True)


if __name__ == "__main__":
    start()
