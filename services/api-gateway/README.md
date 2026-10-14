# api-gateway

Face of the system: validates the upload or product link, writes durable state to
Postgres through SQLAlchemy, and hands the job to `inference-service`.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | DB + transport status |
| POST | `/api/v1/simulations` | `multipart/form-data`: `link` or `file`, room dimensions |
| GET | `/api/v1/simulations/{id}` | status, product profile, Shapely fit report |
| GET | `/api/v1/simulations` | recent jobs |
| POST | `/api/v1/internal/results` | callback used by the workers (requires `x-byb-token`) |

## Poetry

```bash
poetry install                 # includes the editable path dep ../libs/byb-common
poetry run dev                 # reload loop on :8001
poetry run start               # single worker, what the container runs
poetry run test                # pytest against SQLite
poetry run ruff check src tests
```

## Transport

With `DAPR_HTTP_ENDPOINT` set, jobs are published to the `simulation.requested`
Dapr topic. Unset, the gateway calls `inference-service` directly over
`INFERENCE_URL`, so the service runs without a sidecar.
