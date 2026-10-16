"""Wire contracts shared by api-gateway, inference-service and geometry-service."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class JsonModel(BaseModel):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)


class SimulationStatus(StrEnum):
    pending = "pending"
    enriching = "enriching"
    measuring = "measuring"
    completed = "completed"
    failed = "failed"


class ProductGeometry(JsonModel):
    width_cm: float = Field(gt=0, description="Product width in centimetres.")
    depth_cm: float = Field(gt=0, description="Product depth in centimetres.")
    height_cm: float = Field(gt=0, description="Product height in centimetres.")
    clearance_cm: float = Field(default=10.0, ge=0, description="Walkway to keep around the product.")


class ProductProfile(JsonModel):
    name: str
    brand: str | None = None
    category: str = "furniture"
    material: str | None = None
    price_band: str | None = None
    geometry: ProductGeometry
    confidence: float = Field(default=0.5, ge=0, le=1)
    summary: str = ""
    # Provenance: "amd_token_factory" | "heuristic" (not self-hosted vLLM).
    source: str = "heuristic"
    provider: str | None = Field(default=None, description="e.g. amd_token_factory")
    model: str | None = Field(default=None, description="Configured model id when LLM-backed")
    # Per-axis reliability for geometry values that must remain numeric for consumers:
    # verified | extracted | estimated (never claim estimated axes as verified).
    dimension_reliability: dict[str, str] = Field(default_factory=dict)
    measurement_basis: str | None = Field(
        default=None,
        description="listing_verified | listing_partial | category_estimate | amd_token_factory",
    )


class FitPlacement(JsonModel):
    label: str
    ring: list[tuple[float, float]] = Field(description="Polygon ring in metres, room-local coordinates.")
    area_m2: float
    footprint_m2: float
    fits: bool


class FitReport(JsonModel):
    room_area_m2: float
    usable_area_m2: float
    placements: list[FitPlacement] = []
    conflicts: list[str] = []
    coverage_pct: float
    verdict: str


class SimulationRequested(JsonModel):
    """Published by api-gateway; consumed by inference-service."""

    simulation_id: str = Field(min_length=8, max_length=40, description="Gateway simulation id.")
    room_width_m: float = Field(gt=0)
    room_depth_m: float = Field(gt=0)
    room_height_m: float = Field(gt=0)
    product_link: str | None = None
    image_key: str | None = None
    shopper_notes: str | None = None


class SimulationMeasured(JsonModel):
    """Published by inference-service; consumed by geometry-service."""

    simulation_id: str = Field(min_length=8, max_length=40)
    profile: ProductProfile | None = None
    room_width_m: float
    room_depth_m: float
    room_height_m: float


class SimulationCompleted(JsonModel):
    """Posted by geometry-service back to api-gateway."""

    simulation_id: str = Field(min_length=8, max_length=40)
    status: SimulationStatus
    profile: ProductProfile | None = None
    fit: FitReport | None = None
    error: str | None = None
