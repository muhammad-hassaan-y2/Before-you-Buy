# Buy You Before - Geometry Service

Shapely worker. Builds the room polygon, reserves the door swing, then tests the
product footprint against wall support and walkway rules.

## The walkway rule

A face may sit flush on a wall. Every face **not** touching a wall must keep at least
`max(clearance_cm, MIN_WALKWAY_M)` metres free, otherwise the placement is reported
`fits=false` with the binding side named in `conflicts`.

Verdicts: `fits` (a compliant placement exists), `tight` (it lands, but the walkway
fails), `too_large` (footprint cannot fit at all).

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | transport status |
| POST | `/v1/measure` | synchronous `SimulationMeasured` -> `FitReport` |
| POST | `/events` | Dapr subscription target for `simulation.measured` |

Results are always posted back to the gateway at `/api/v1/internal/results` with the
`x-byb-token` header, in Dapr and direct modes alike.

## Poetry

```bash
poetry install
poetry run dev            # :8003
poetry run start
poetry run test
```
