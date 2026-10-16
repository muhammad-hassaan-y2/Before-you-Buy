"""Put the shop's catalog where the Evolus agent can read it.

    poetry run python -m byb_agent.evolus_seed

One markdown document per SKU, indexed into `EVOLUS_LIBRARY_ID`. The catalog stays the
source of truth: this copies what catalog-service already serves rather than a hand-written
list that could drift from it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from byb_agent.evolus import Evolus, EvolusError
from byb_agent.pipeline import Pipeline
from byb_agent.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("byb.seed")


def document(row: dict[str, Any]) -> str:
    geometry = row.get("geometry") or {}
    lines = [
        f"# {row.get('name', row.get('sku'))}",
        "",
        f"- SKU: `{row.get('sku')}`",
        f"- Brand: {row.get('brand') or '-'}",
        f"- Category: {row.get('category')}",
        f"- Material: {row.get('material') or '-'}",
        f"- Price band: {row.get('price_band') or '-'}",
        f"- Size: {geometry.get('width_cm')} × {geometry.get('depth_cm')} × {geometry.get('height_cm')} cm",
        f"- Clearance it needs: {geometry.get('clearance_cm')} cm",
    ]
    if row.get("url"):
        lines.append(f"- Listing: {row['url']}")
    return "\n".join(lines) + "\n"


async def main() -> int:
    if not settings.evolus_library_id:
        logger.error("EVOLUS_LIBRARY_ID is not set - create the knowledge library in the workspace first.")
        return 1
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0)) as client:
        pipeline, evolus = Pipeline(client, settings), Evolus(client, settings)
        if not evolus.credentials:
            logger.error("EVOLUS_API_KEY and EVOLUS_APP_ID are required.")
            return 1
        rows = await pipeline.catalog()
        indexed = 0
        for row in rows:
            try:
                await evolus.index_document(settings.evolus_library_id, f"{row.get('sku')}.md", document(row).encode())
                indexed += 1
            except EvolusError as exc:
                logger.warning("%s was not indexed: %s", row.get("sku"), exc)
        logger.info("indexed %d/%d SKUs into library %s", indexed, len(rows), settings.evolus_library_id)
        return 0 if indexed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
