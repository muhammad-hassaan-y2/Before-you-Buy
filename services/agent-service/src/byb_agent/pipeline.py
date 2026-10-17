"""The agent's hands: it drives the same HTTP surface a shopper's browser uses.

Nothing bypasses the gateway. A fit the agent reports is a fit the six-service pipeline
produced, which is what makes the recommendation defensible to a merchant.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from byb_agent.settings import Settings

logger = logging.getLogger("byb.pipeline")

SETTLED = {"completed", "failed"}


class PipelineError(RuntimeError):
    """The pipeline could not be reached or refused the job."""


class Pipeline:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    @property
    def gateway(self) -> str:
        return self._settings.gateway_url.rstrip("/")

    async def catalog(self) -> list[dict[str, Any]]:
        response = await self._client.get(f"{self.gateway}/api/v1/catalog", timeout=20)
        response.raise_for_status()
        return list(response.json())

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
        form: dict[str, Any] = {
            "room_width_m": room_width_m,
            "room_depth_m": room_depth_m,
            "room_height_m": room_height_m,
        }
        if link:
            form["link"] = link
        if notes:
            form["shopper_notes"] = notes
        if image_key:
            # The shopper's room photo, already stored by the gateway: every candidate is fitted
            # into the room vision-service measures from it, not into a typed guess.
            form["image_key"] = image_key
        try:
            response = await self._client.post(f"{self.gateway}/api/v1/simulations", data=form, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PipelineError(f"could not queue a simulation: {exc}") from exc
        return str(response.json()["id"])

    async def simulation(self, simulation_id: str) -> dict[str, Any]:
        response = await self._client.get(f"{self.gateway}/api/v1/simulations/{simulation_id}", timeout=20)
        response.raise_for_status()
        return dict(response.json())

    async def wait(self, simulation_id: str) -> dict[str, Any]:
        """Poll until the chain settles. Bounded by the settings, so a stalled worker cannot hang a run."""
        deadline = self._settings.settle_timeout_s / self._settings.poll_interval_s
        for _ in range(int(deadline)):
            detail = await self.simulation(simulation_id)
            if detail.get("status") in SETTLED:
                return detail
            await asyncio.sleep(self._settings.poll_interval_s)
        return await self.simulation(simulation_id)
