"""In-process run store.

Deliberately not a table: the gateway owns durable state, and a journey is a working
transcript - a trace the browser polls while the run is live. On restart the transcript is
gone but every simulation it triggered is still in Postgres, reachable by id.

Reservations follow the same rule and carry the fit proof with them, so a lost hold can always
be re-taken from the simulation it points at.
"""

from __future__ import annotations

from collections import OrderedDict

from byb_agent.contracts import AgentRun, Reservation


class RunStore:
    def __init__(self, keep: int = 100) -> None:
        self._runs: OrderedDict[str, AgentRun] = OrderedDict()
        self._keep = keep

    def put(self, run: AgentRun) -> AgentRun:
        self._runs[run.id] = run
        self._runs.move_to_end(run.id)
        while len(self._runs) > self._keep:
            self._runs.popitem(last=False)
        return run

    def get(self, run_id: str) -> AgentRun | None:
        return self._runs.get(run_id)

    def recent(self, limit: int = 20) -> list[AgentRun]:
        runs = list(self._runs.values())[-limit:]
        runs.reverse()
        return runs

    def __len__(self) -> int:
        return len(self._runs)


class Reservations:
    """The holds a shopper has asked for, newest first, waiting on a person at the shop."""

    def __init__(self, keep: int = 200) -> None:
        self._items: OrderedDict[str, Reservation] = OrderedDict()
        self._keep = keep

    def put(self, reservation: Reservation) -> Reservation:
        self._items[reservation.id] = reservation
        self._items.move_to_end(reservation.id)
        while len(self._items) > self._keep:
            self._items.popitem(last=False)
        return reservation

    def get(self, reservation_id: str) -> Reservation | None:
        return self._items.get(reservation_id)

    def recent(self, limit: int = 20) -> list[Reservation]:
        items = list(self._items.values())[-limit:]
        items.reverse()
        return items

    def __len__(self) -> int:
        return len(self._items)
