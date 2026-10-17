from __future__ import annotations

from typing import Any

import pytest

from byb_agent.evolus import EvolusError
from byb_agent.runs import RunStore
from byb_agent.settings import Settings
from byb_agent.tools import Tools


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gateway_url="http://gateway",
        catalog_url="http://catalog",
        evolus_api_key="sk_test",
        evolus_app_id="space-1",
        evolus_agent_id="agent-1",
        evolus_reply_tool="",
        vllm_base_url="",
        max_candidates=3,
        parallel_fits=2,
        settle_timeout_s=6,
        poll_interval_s=0.01,
    )


def row(sku: str, name: str, category: str, band: str, width_cm: float, depth_cm: float, height_cm: float, material: str = "oak") -> dict:
    return {
        "sku": sku,
        "name": name,
        "brand": name.split()[0].lower(),
        "category": category,
        "material": material,
        "price_band": band,
        "geometry": {"width_cm": width_cm, "depth_cm": depth_cm, "height_cm": height_cm, "clearance_cm": 10.0},
    }


@pytest.fixture
def rows() -> list[dict]:
    return [
        row("SOF-001", "Linen three-seater sofa", "sofa", "$$", 220, 95, 85, "linen"),
        row("SOF-002", "Compact two-seater sofa", "sofa", "$", 160, 88, 80, "linen"),
        row("SOF-003", "Velvet large sofa", "sofa", "$$$", 280, 105, 90, "velvet"),
        row("ARM-001", "Oak armchair", "armchair", "$$", 75, 80, 95),
        row("BCK-001", "Tall bookcase", "bookcase", "$", 80, 28, 202),
    ]


class StubPipeline:
    """The six-service pipeline as the agent sees it: a catalog, a queue, a verdict.

    Verdicts come from a table keyed by the link that was queued, so a test says which product
    fits which room instead of trusting real geometry to repeat itself.
    """

    def __init__(self, rows: list[dict], verdicts: dict[str, str] | None = None, crash: set[str] | None = None) -> None:
        self._rows = rows
        self._verdicts = verdicts or {}
        self._crash = crash or set()
        self.started: list[dict[str, Any]] = []
        self._sku_by_id: dict[str, str] = {}
        self._photo: dict[str, bool] = {}
        self._next = 0

    async def catalog(self) -> list[dict]:
        return self._rows

    async def start_simulation(
        self,
        *,
        link: str | None = None,
        notes: str | None = None,
        room_width_m: float,
        room_depth_m: float,
        room_height_m: float,
        image_key: str | None = None,
    ) -> str:
        self.started.append(
            {
                "link": link,
                "notes": notes,
                "room": (room_width_m, room_depth_m, room_height_m),
                "image_key": image_key,
            }
        )
        self._next += 1
        simulation_id = f"sim{self._next:04d}"
        self._photo[simulation_id] = bool(image_key)
        # The journey names the SKU it queued, which is how a test maps a verdict back to a product.
        for item in self._rows:
            if notes and f"shortlisted {item['sku']}" in notes:
                self._sku_by_id[simulation_id] = str(item["sku"])
        return simulation_id

    def _scan(self, simulation_id: str) -> dict[str, Any]:
        """A photo-measured room comes back smaller than the numbers the shopper typed."""
        if self._photo.get(simulation_id):
            return {"width_m": 3.6, "depth_m": 3.0, "height_m": 2.4, "method": "photo", "measured": True, "obstacles": []}
        return {"width_m": 4.0, "depth_m": 3.5, "method": "declared", "obstacles": []}

    async def simulation(self, simulation_id: str) -> dict[str, Any]:
        sku = self._sku_by_id.get(simulation_id, "")
        verdict = self._verdicts.get(sku or "", self._verdicts.get("default", "fits"))
        if sku in self._crash:
            return {"id": simulation_id, "status": "failed", "error": "geometry-service unavailable", "has_model": False, "fit_report": None}
        row = next((item for item in self._rows if str(item["sku"]) == sku), None)
        geometry = (row or {}).get("geometry") or {"width_cm": 200, "depth_cm": 90, "height_cm": 85}
        fits = verdict in {"fits", "tight"}
        return {
            "id": simulation_id,
            "status": "completed",
            "error": None,
            "has_model": True,
            "product_link": f"https://shop.example.com/p/{sku.lower()}/",
            "room_width_m": 4.0,
            "room_depth_m": 3.5,
            "room_height_m": 2.4,
            "product_profile": {"name": sku, "geometry": geometry, "confidence": 0.7},
            "catalog_candidate": {
                "sku": sku,
                "name": (row or {}).get("name", sku),
                "brand": (row or {}).get("brand", ""),
                "category": (row or {}).get("category", "furniture"),
                "price_band": (row or {}).get("price_band"),
                "geometry": geometry,
                "score": 1.0,
            },
            "room_scan": self._scan(simulation_id),
            "fit_report": {
                "room_area_m2": 14.0,
                "usable_area_m2": 13.3,
                "verdict": verdict,
                "coverage_pct": 12.5,
                "conflicts": [] if fits else ["the door swing is blocked"],
                "suggestions": [] if fits else ["try a piece no wider than 180 cm"],
                "door_swing_m": 0.85,
                "door_pass": "pass" if fits else "blocked",
                "walkway_connected": fits,
                "isolated_pockets": 0 if fits else 1,
                "fragile": False,
                "tolerance_cm": 2.0,
                "placements": [
                    {
                        "label": "back wall",
                        "fits": fits,
                        "footprint_m2": round(float(geometry["width_cm"]) * float(geometry["depth_cm"]) / 10000, 3),
                        "walkway_m": {"left": 0.9, "right": 0.7, "front": 1.2, "back": 0.0},
                    },
                    {
                        "label": "side wall",
                        "fits": False,
                        "footprint_m2": 1.0,
                        "walkway_m": {"left": 0.2, "right": 0.2, "front": 0.2, "back": 0.2},
                    },
                ],
            },
        }

    async def wait(self, simulation_id: str) -> dict[str, Any]:
        return await self.simulation(simulation_id)


class StubEvolus:
    def __init__(self, credentials: bool = True, answer: str = "On it.", fail: bool = False) -> None:
        self.credentials = credentials
        self.answer = answer
        self.fail = fail
        self.prompts: list[str] = []
        self.tools: list[str] = []
        self.workflows: list[str] = []

    @property
    def agent_model(self) -> str | None:
        return "space-1:agent-1" if self.credentials else None

    async def ask(self, prompt: str, *, system: str | None = None, conversation_id: str | None = None) -> tuple[str, str | None]:
        self.prompts.append(prompt)
        if self.fail:
            raise EvolusError("evolus chat -> 500: boom")
        return self.answer, conversation_id or "conv-9"

    async def execute_workflow(self, workflow_id: str, text: str, *, params=None, files=None, callback_url: str | None = None) -> dict:
        self.workflows.append(workflow_id)
        return {"executionId": "exec-42", "traceId": "trace-7"}

    async def run_tool(self, tool: str, text: str, options: dict | None = None) -> str:
        self.tools.append(tool)
        if self.fail:
            raise EvolusError("402 Payment Required")
        return f"[{tool}] {text}"


class StubModel:
    def __init__(self, configured: bool = False, data: dict | None = None, answer: str = "the sofa will fit") -> None:
        self.configured = configured
        self._data = data
        self._answer = answer
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return "Qwen/Qwen2.5-7B-Instruct" if self.configured else ""

    async def read_json(self, prompt: str) -> dict | None:
        self.prompts.append(prompt)
        return self._data

    async def complete(self, prompt: str, *, system: str = "", max_tokens: int = 512) -> str:
        self.prompts.append(prompt)
        return self._answer


@pytest.fixture
def pipeline(rows) -> StubPipeline:
    return StubPipeline(rows)


@pytest.fixture
def evolus() -> StubEvolus:
    return StubEvolus()


@pytest.fixture
def model() -> StubModel:
    return StubModel()


@pytest.fixture
def store() -> RunStore:
    return RunStore()


@pytest.fixture
def tools(pipeline, evolus, model, store, settings) -> Tools:
    return Tools(pipeline, evolus, model, store, settings)  # type: ignore[arg-type]
