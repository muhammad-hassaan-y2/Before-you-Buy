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


class Reservation(JsonModel):
    """A hold a shopper asked for on a piece the pipeline proved fits.

    Not an order: nothing is charged and nothing ships. It is the record a merchant accepts,
    and it carries the words the confirmation came in, so a person can audit the gate.
    """

    id: str
    simulation_id: str
    sku: str | None = None
    name: str | None = None
    verdict: str | None = None
    confirmation: str = Field(description="What the human said, verbatim.")
    status: str = Field(default="pending_merchant", description="pending_merchant, accepted or released.")
    created_at: str = ""


class BriefRequest(JsonModel):
    """The input the UI, the widget or a webhook posts to start a run."""

    brief: str = Field(min_length=3, description="Shopper words: what they want, for which room, at what budget.")
    room_width_m: float | None = None
    room_depth_m: float | None = None
    room_height_m: float | None = None
    image_key: str | None = Field(default=None, description="Room photo already stored by the gateway.")


class CartLine(JsonModel):
    """One piece in the bag: the price the catalog quoted, and the fit the engine proved behind it.

    `verdict` is the geometry engine's word for the room in `room`, or None when nothing has been
    measured. Checkout reads that field, so an unproven line is visible rather than silently sold.
    """

    sku: str
    name: str
    quantity: int = Field(default=1, ge=1)
    price_eur: float = Field(description="What the shop lists it at, from the catalog's own terms.")
    cost_eur: float = Field(description="What the supplier's side of the dropship costs the shop.")
    lead_days: int = 0
    freight: str = "parcel"
    volume_m3: float = 0.0
    simulation_id: str | None = None
    verdict: str | None = None
    coverage_pct: float = 0.0
    walkway_m: dict[str, float] = Field(default_factory=dict)
    footprint_m2: float = 0.0
    placement_proved: bool = Field(default=False, description="False when the footprint is only the catalog box, not a placement the engine cleared.")
    room: dict | None = Field(default=None, description="The room this verdict was measured in; a line in another room is re-measured.")
    added_at: str = ""


class Cart(JsonModel):
    """A bag an agent and a browser can both be holding.

    Deliberately not a cookie: the id comes back from every cart tool, so the shopper's ChatGPT,
    their Claude and the shop's own page can add to, measure and check out one bag.
    """

    id: str
    lines: list[CartLine] = Field(default_factory=list)
    room: dict | None = None
    usable_area_m2: float = Field(default=0.0, description="Floor the room actually offers, from the engine's own reports.")
    updated_at: str = ""


class Order(JsonModel):
    """What checkout writes: a signed order *draft*, not a payment.

    Every line carries the simulation that proved it and the shopper's own words that let the
    order be placed. No card is touched and nothing ships from this service - a person at the shop
    accepts the draft, which is the same gate a hold uses.
    """

    id: str
    cart_id: str
    lines: list[CartLine] = Field(default_factory=list)
    currency: str = "EUR"
    total_eur: float = 0.0
    cost_eur: float = 0.0
    margin_eur: float = 0.0
    volume_m3: float = 0.0
    lead_days: int = 0
    freight: str = "parcel"
    confirmation: str = Field(description="What the shopper said, verbatim.")
    confirmed_through: str = "relayed by the agent"
    status: str = Field(default="awaiting_merchant", description="awaiting_merchant, accepted or released.")
    created_at: str = ""
    proofs: list[dict] = Field(default_factory=list, description="One entry per line: the simulation that cleared it and the room it cleared.")
    combined: dict | None = Field(default=None, description="The set verdict - footprints and walkways added across the bag.")
    room: dict | None = None
