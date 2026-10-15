"""Wire contracts shared by every Buy You Before service.

The pipeline is linear, one topic per hop:

    simulation.requested   -> catalog-service    (link/notes -> SKU candidate)
    simulation.catalogued  -> inference-service  (candidate + listing -> ProductProfile)
    simulation.measured    -> vision-service     (room photo -> dimensions + obstacles)
    simulation.room_scanned-> geometry-service   (Shapely placements)
    simulation.fitted      -> scene-service      (SceneSpec + glTF) -> gateway results
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class JsonModel(BaseModel):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)


class SimulationStatus(StrEnum):
    pending = "pending"
    cataloguing = "cataloguing"
    enriching = "enriching"
    measuring = "measuring"
    scanning = "scanning"
    fitting = "fitting"
    rendering = "rendering"
    completed = "completed"
    failed = "failed"


class ProductGeometry(JsonModel):
    width_cm: float = Field(gt=0, description="Product width in centimetres.")
    depth_cm: float = Field(gt=0, description="Product depth in centimetres.")
    height_cm: float = Field(gt=0, description="Product height in centimetres.")
    clearance_cm: float = Field(default=10.0, ge=0, description="Walkway to keep around the product.")


class ProductPart(JsonModel):
    """A box the 3D engine can assemble into a recognisable piece of furniture."""

    label: str
    size_cm: tuple[float, float, float] = Field(description="width, depth, height in centimetres.")
    offset_cm: tuple[float, float, float] = Field(description="Centre of the box relative to the product origin.")
    tone: str = Field(default="upholstery", description="Named material in the scene's palette.")


class ProductProfile(JsonModel):
    name: str
    brand: str | None = None
    category: str = "furniture"
    material: str | None = None
    price_band: str | None = None
    geometry: ProductGeometry
    confidence: float = Field(default=0.5, ge=0, le=1)
    summary: str = ""
    source: str = "vllm"
    parts: list[ProductPart] = Field(default_factory=list, description="Empty means the engine builds one box.")


class CatalogCandidate(JsonModel):
    """The closest SKU catalog-service found for a link or free-text notes."""

    sku: str
    name: str
    brand: str
    category: str
    material: str | None = None
    price_band: str | None = None
    geometry: ProductGeometry
    parts: list[ProductPart] = Field(default_factory=list)
    score: float = Field(ge=0, le=1, description="Match confidence, 0 when nothing matched.")
    source: str = "catalog"


class Obstacle(JsonModel):
    """Floor space the product cannot use, in room-local metres."""

    label: str
    ring: list[tuple[float, float]] = Field(description="Polygon ring in metres.")
    height_m: float = Field(default=0.0, ge=0, description="0 means treat it as full height.")
    source: str = "declared"


class RoomScan(JsonModel):
    """Vision-service output. `measured` is false when the photo could not be read."""

    width_m: float = Field(gt=0)
    depth_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    obstacles: list[Obstacle] = Field(default_factory=list)
    measured: bool = False
    method: str = "declared"
    confidence: float = Field(default=0.0, ge=0, le=1)


class FitPlacement(JsonModel):
    label: str
    ring: list[tuple[float, float]] = Field(description="Polygon ring in metres, room-local coordinates.")
    area_m2: float
    footprint_m2: float
    fits: bool
    centre_x_m: float = 0.0
    centre_y_m: float = 0.0
    rotation_deg: float = Field(default=0.0, description="0 or 90, the orientation the box is drawn at.")
    walkway_m: dict[str, float] = Field(default_factory=dict, description="Gap to each face: left/right/front/back.")


class FitReport(JsonModel):
    room_area_m2: float
    usable_area_m2: float
    placements: list[FitPlacement] = []
    conflicts: list[str] = []
    coverage_pct: float
    verdict: str
    obstacles: list[Obstacle] = Field(default_factory=list)
    door_swing_m: float = Field(default=0.85, description="Quarter-circle the room door sweeps; geometry owns the value.")


class SceneCamera(JsonModel):
    label: str
    position_m: tuple[float, float, float]
    target_m: tuple[float, float, float]
    fov_deg: float = 50.0


class ScenePlacement(JsonModel):
    label: str
    fits: bool
    position_m: tuple[float, float, float] = Field(description="Product origin in scene metres: x across the room, 0 on the floor, z away from the door wall.")
    rotation_deg: float = Field(default=0.0, description="Turn about the room's vertical axis. Apply it as -rotation_deg on the scene y axis: product-local (x, y, z) maps to scene (x, z, y).")
    walkway_m: dict[str, float] = Field(default_factory=dict)


class SceneSpec(JsonModel):
    """Everything the browser engine needs, in metres, right-handed y-up, room origin in
    the corner beside the hinge, product parts in centimetres (x width, y depth, z up)."""

    version: str = "1"
    room_width_m: float
    room_depth_m: float
    room_height_m: float
    walls: list[Obstacle] = Field(default_factory=list, description="Obstacles already inside the room.")
    door_swing_m: float = 0.85
    product_name: str
    product_category: str = "furniture"
    parts: list[ProductPart] = Field(default_factory=list)
    geometry: ProductGeometry
    clearance_m: float = 0.1
    placements: list[ScenePlacement] = Field(default_factory=list)
    cameras: list[SceneCamera] = Field(default_factory=list)
    verdict: str = "fits"
    coverage_pct: float = 0.0


class SimulationRequested(JsonModel):
    """Published by api-gateway; consumed by catalog-service."""

    simulation_id: str = Field(min_length=8, max_length=40, description="Gateway simulation id.")
    room_width_m: float = Field(gt=0)
    room_depth_m: float = Field(gt=0)
    room_height_m: float = Field(gt=0)
    product_link: str | None = None
    image_key: str | None = None
    shopper_notes: str | None = None


class SimulationCatalogued(JsonModel):
    """Published by catalog-service; consumed by inference-service."""

    simulation_id: str = Field(min_length=8, max_length=40)
    room_width_m: float
    room_depth_m: float
    room_height_m: float
    product_link: str | None = None
    image_key: str | None = None
    shopper_notes: str | None = None
    candidate: CatalogCandidate | None = None


class SimulationMeasured(JsonModel):
    """Published by inference-service; consumed by vision-service."""

    simulation_id: str = Field(min_length=8, max_length=40)
    profile: ProductProfile | None = None
    candidate: CatalogCandidate | None = None
    room_width_m: float
    room_depth_m: float
    room_height_m: float
    image_key: str | None = None


class SimulationRoomScanned(JsonModel):
    """Published by vision-service; consumed by geometry-service."""

    simulation_id: str = Field(min_length=8, max_length=40)
    profile: ProductProfile | None = None
    candidate: CatalogCandidate | None = None
    scan: RoomScan


class SimulationFitted(JsonModel):
    """Published by geometry-service; consumed by scene-service."""

    simulation_id: str = Field(min_length=8, max_length=40)
    profile: ProductProfile | None = None
    candidate: CatalogCandidate | None = None
    scan: RoomScan | None = None
    fit: FitReport | None = None


class SimulationProgress(JsonModel):
    """A worker telling the gateway which stage it has reached."""

    simulation_id: str = Field(min_length=8, max_length=40)
    status: SimulationStatus


class SimulationCompleted(JsonModel):
    """Posted by scene-service back to api-gateway."""

    simulation_id: str = Field(min_length=8, max_length=40)
    status: SimulationStatus
    profile: ProductProfile | None = None
    candidate: CatalogCandidate | None = None
    scan: RoomScan | None = None
    fit: FitReport | None = None
    scene: SceneSpec | None = None
    gltf: dict | None = Field(default=None, description="glTF 2.0 document for the .glb download.")
    error: str | None = None
