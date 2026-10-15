"""Response shapes for the browser-facing API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SimulationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    product_link: str | None = None
    image_key: str | None = None
    created_at: datetime
    error: str | None = None


class SimulationDetail(SimulationSummary):
    room_width_m: float
    room_depth_m: float
    room_height_m: float
    shopper_notes: str | None = None
    updated_at: datetime
    product_profile: dict | None = None
    catalog_candidate: dict | None = None
    room_scan: dict | None = None
    fit_report: dict | None = None


class SimulationAccepted(BaseModel):
    id: str
    status: str
    detail: str = Field(default="Simulation queued. Poll GET /api/v1/simulations/{id}.")


class HealthResponse(BaseModel):
    service: str
    status: str
    database: str
    dapr: str
    transport: str
