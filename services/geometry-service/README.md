# Before You Buy - Geometry Service

Shapely worker. Builds the room polygon, reserves the door swing and whatever
vision-service found on the floor, then tests the product footprint against wall
support and walkway rules.

## The walkway rule

A face may sit flush on a wall. Every face **not** touching a wall must keep at least
`max(clearance_cm, MIN_WALKWAY_M)` metres free, otherwise the placement is reported
`fits=false` with the binding side named in `conflicts`.

Verdicts: `fits` (a compliant placement exists), `tight` (it lands, but the walkway
fails), `blocked` (every candidate hits the swing or existing furniture), `too_large`
(footprint cannot fit at all). Each placement carries its centre, orientation and the
gap on all four faces, which is what the browser engine draws.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | transport status |
| POST | `/v1/fit` | synchronous `SimulationRoomScanned` -> `FitReport` |
| POST | `/events` | Dapr subscription target for `simulation.room_scanned` |

Outcomes are published to `simulation.fitted` for scene-service to finish, or POSTed
straight to scene-service `/v1/render` when no sidecar is present. The one case that
reports to the gateway itself is a message that arrived without a product profile: there
is nothing downstream could do with it.

## Poetry

```bash
poetry install
poetry run dev            # :8003
poetry run start
poetry run test
```
