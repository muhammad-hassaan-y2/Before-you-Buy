"""Agent-side contracts.

These describe what the agent *does*, not what the pipeline measures: the pipeline's own
shapes live in `byb_common.contracts` and are embedded here as-is, so a run trace carries
real fit reports rather than a paraphrase of them.
"""

from __future__ import annotations

from pydantic import Field

from byb_common.contracts import CatalogCandidate, FitReport, JsonModel, ProductProfile, RoomScan


class ShopperBrief(JsonModel):
    """What the shopper actually asked for, resolved to something the catalog can be searched with."""

    raw: str = Field(description="The shopper's own words, kept so a person can audit the decision.")
    category: str | None = None
    price_band: str | None = Field(default=None, description="$, $$ or $$$ as the catalog spells them.")
    budget_eur: float | None = None
    room_width_m: float | None = None
    room_depth_m: float | None = None
    room_height_m: float | None = None
    must_haves: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: str = Field(default="heuristic", description="evolus, model or heuristic - which reader produced this.")


class AgentStep(JsonModel):
    """One node of the run trace: what ran, what came back, and how long it took."""

    index: int
    kind: str = Field(description="intake, brief, shortlist, simulate, compare, reply or handoff.")
    status: str = Field(default="ok", description="ok, branch, skipped or failed.")
    detail: str = ""
    tool: str | None = Field(default=None, description="Tool or Evolus endpoint that produced this step.")
    group: str | None = Field(default=None, description="Set for steps that ran inside one parallel fan-out.")
    iteration: int = Field(default=1, description="Loop pass this step belongs to; 1 for straight-line steps.")
    ms: int = 0
    output: dict | None = None


class FitAttempt(JsonModel):
    """The evidence for one SKU: the geometry that was tested and what the pipeline said."""

    sku: str
    name: str
    price_band: str | None = None
    score: float = 0.0
    simulation_id: str | None = None
    status: str = "queued"
    verdict: str | None = None
    coverage_pct: float = 0.0
    walkway_m: dict[str, float] = Field(default_factory=dict)
    reason: str | None = None


class AgentDecision(JsonModel):
    """The branch the agent took at the end, with the reason a person can check."""

    action: str = Field(description="recommend, alternatives or handoff.")
    sku: str | None = None
    simulation_id: str | None = None
    confidence: float = 0.0
    reason: str = ""
    evidence: dict | None = None


class AgentRun(JsonModel):
    id: str
    status: str = Field(default="running", description="running, done, awaiting_human or failed.")
    brief: ShopperBrief | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    candidates: list[CatalogCandidate] = Field(default_factory=list)
    attempts: list[FitAttempt] = Field(default_factory=list)
    decision: AgentDecision | None = None
    reply: str | None = None
    profile: ProductProfile | None = None
    scan: RoomScan | None = None
    fit: FitReport | None = None
    evolus_execution_id: str | None = None
    conversation_id: str | None = None
    callback: dict | None = Field(default=None, description="What an Evolus workflow posted back to /agent/webhooks/evolus.")
    error: str | None = None


class BriefRequest(JsonModel):
    """The input the UI, the widget or a webhook posts to start a run."""

    brief: str = Field(min_length=3, description="Shopper words: what they want, for which room, at what budget.")
    room_width_m: float | None = None
    room_depth_m: float | None = None
    room_height_m: float | None = None
    image_key: str | None = Field(default=None, description="Room photo already stored by the gateway.")
