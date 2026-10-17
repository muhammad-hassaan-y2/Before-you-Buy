"""On-hand stock, and the only two things that are allowed to change it.

No warehouse feed is connected, so a count is derived from the SKU the same way the price is —
same SKU in, same count out — and after that it moves for a reason the storefront can name: a
hold a shopper agreed to, or an order draft a person at the shop has not accepted yet. Nothing
here ticks on a timer, because a number that moves by itself is a lie with an animation.

The ledger is per process. A restart puts the pieces back on the shelf, which is what a demo
shop should do and what a real one would do from a database instead.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from byb_catalog.commerce import lead_days, terms_for, volume_m3
from byb_catalog.skus import CATALOG, Sku

# A pallet of a three-seat sofa is not something the shop keeps twenty of in a corridor.
PALLET_DEPTH = 5
PARCEL_DEPTH = 24

# Below this many units the storefront says "low" rather than counting them out loud.
LOW_WATERMARK = 3

# Anything slower than this is cut after the order, not picked from a shelf.
MADE_TO_ORDER_DAYS = 24

EVENTS_KEPT = 40


def _slot(sku: str) -> int:
    """A stable 0-23 pick per SKU, so a count never changes between two reads of the same shop."""
    return sum(ord(char) for char in sku) % 24


def on_hand_for(item: Sku) -> int:
    """How many the shop would have on the floor, from the box it ships in and how long it takes."""
    if lead_days(item) >= MADE_TO_ORDER_DAYS:
        return 0
    depth = PALLET_DEPTH if terms_for(item)["freight"] == "pallet" else PARCEL_DEPTH
    return max(0, depth - _slot(item.sku) % depth)


def stock_state(available: int, item: Sku) -> str:
    if available <= 0:
        return "made_to_order" if lead_days(item) >= MADE_TO_ORDER_DAYS else "backorder"
    if available <= LOW_WATERMARK:
        return "low"
    return "in_stock"


@dataclass
class Claim:
    """Units taken off the shelf by one thing the shop did, keyed so a retry does not double-count."""

    key: str
    reason: str
    lines: list[dict[str, Any]]
    at: str


@dataclass
class Ledger:
    """The claims, and the counts they move."""

    _claims: dict[str, Claim] = field(default_factory=dict)
    _events: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reserved(self, sku: str) -> int:
        wanted = sku.strip().lower()
        return sum(
            int(line["qty"])
            for claim in self._claims.values()
            for line in claim.lines
            if str(line["sku"]).lower() == wanted
        )

    def claim(self, *, key: str, lines: list[dict[str, Any]], reason: str) -> Claim:
        """Take these units. Idempotent by key, and it refuses the whole claim over one short line."""
        with self._lock:
            existing = self._claims.get(key)
            if existing is not None:
                return existing
            wanted: dict[str, int] = {}
            for line in lines:
                sku = str(line["sku"]).strip().lower()
                qty = max(int(line.get("qty", 1)), 1)
                wanted[sku] = wanted.get(sku, 0) + qty
            known = {c.sku.lower(): c for c in CATALOG}
            missing = sorted(sku for sku in wanted if sku not in known)
            if missing:
                raise KeyError(f"no SKU {', '.join(missing)}")
            for sku, qty in wanted.items():
                row = known[sku]
                free = on_hand_for(row) - self.reserved(row.sku)
                if qty > free:
                    raise ValueError(f"{row.sku} has {free} of {on_hand_for(row)} on the shelf; {qty} asked for.")
            claim = Claim(
                key=key,
                reason=reason,
                lines=[{"sku": row.sku, "qty": wanted[row.sku.lower()]} for row in CATALOG if row.sku.lower() in wanted],
                at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            self._claims[key] = claim
            for line in claim.lines:
                self._log("claimed", line["sku"], line["qty"], reason, key)
            return claim

    def release(self, key: str) -> bool:
        """Put a claim's units back. True when there was a claim by that key to put back."""
        with self._lock:
            claim = self._claims.pop(key, None)
            if claim is None:
                return False
            for line in claim.lines:
                self._log("released", line["sku"], line["qty"], claim.reason, key)
            return True

    def _log(self, action: str, sku: str, qty: int, reason: str, key: str) -> None:
        self._events.append(
            {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "action": action, "sku": sku, "qty": qty, "reason": reason, "key": key}
        )
        del self._events[:-EVENTS_KEPT]

    def events(self) -> list[dict[str, Any]]:
        return list(reversed(self._events))

    def claims(self) -> list[dict[str, Any]]:
        return [claim.__dict__ for claim in sorted(self._claims.values(), key=lambda c: c.at, reverse=True)]


LEDGER = Ledger()


def stock_row(item: Sku) -> dict[str, Any]:
    """One shelf's worth of truth: what is there, what is held, and when the next lot lands."""
    on_hand = on_hand_for(item)
    held = LEDGER.reserved(item.sku)
    available = max(on_hand - held, 0)
    terms = terms_for(item)
    lead = int(terms["lead_days"])
    return {
        "sku": item.sku,
        "name": item.name,
        "on_hand": on_hand,
        "reserved": held,
        "available": available,
        "state": stock_state(available, item),
        "volume_m3": volume_m3(item),
        "lead_days": lead,
        # The date the next lot is on the floor, not a promise about a truck already rolling.
        "next_lot_in_days": lead if available == 0 else max(lead // 3, 2),
        "basis": "derived from the SKU's box and freight; moved only by a hold or an order draft",
    }


def browse() -> list[dict[str, Any]]:
    return [stock_row(item) for item in CATALOG]


def read(sku: str) -> dict[str, Any] | None:
    wanted = sku.strip().lower()
    item = next((row for row in CATALOG if row.sku.lower() == wanted), None)
    return stock_row(item) if item else None


def eta(days: int) -> str:
    """A date the storefront can print, so 'in 9 days' is not left to the shopper to work out."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
