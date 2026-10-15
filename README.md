# Buy You Before — Room Simulator

Check whether a piece of furniture actually fits your room **before** you buy it.
Paste a product link (or upload a room photo), and the stack works out the item's real
dimensions and tests its footprint against your walls, door swing and walkway.

Three FastAPI services, one Next.js app, Postgres for state, Dapr for the transport and
vLLM (AMD ROCm) for product understanding.

```
browser ──> Next.js :3000 ──/api/v1──> api-gateway :8001 ──SQLAlchemy──> Postgres
                                            │  simulation.requested (Dapr pub/sub)
                                            ▼
                                     inference-service :8002 ──HTTP──> vLLM (ROCm)
                                            │  simulation.measured (Dapr pub/sub)
                                            ▼
                                     geometry-service :8003 ──Shapely──> fit report
                                            │  POST /api/v1/internal/results
                                            ▼
                                       api-gateway (persists, browser polls)
```

## Layout

```
components/                     Dapr components (Redis pub/sub)
libs/byb-common/                shared event contracts + Dapr transport shim
services/api-gateway/           FastAPI, SQLAlchemy models, ingest and job state
services/inference-service/     vLLM product dimensions, heuristic fallback
services/geometry-service/      Shapely fit analysis and placement candidates
frontend/                       Next.js 16 app, page at /room-simulator
docker-compose.yml              postgres + redis + 3 services + 3 daprd + vllm + frontend
Makefile                        up / down / logs / build / test / install
scripts/e2e-smoke.sh            drives one full simulation without Docker
```

## Quick start (Docker, Linux)

```bash
cp .env.example .env
docker compose up --build          # no GPU: vLLM stays down, heuristics fill in
docker compose --profile gpu up    # with an AMD ROCm host (/dev/kfd, /dev/dri)
```

Then open <http://localhost:3000/room-simulator>.

Useful targets: `make up PROFILE=gpu`, `make logs`, `make down`, `make clean` (drops
volumes), `make rebuild`.

## Local development (no Docker)

Postgres is the only supported database at runtime. Start it on its own and point the
gateway at it; the services then talk over plain HTTP.

```bash
docker compose up -d postgres redis       # :5432 and :6379
export DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/beforeyoubuy
```

```bash
# each service has its own Poetry project
make install                                  # or run `poetry install` per directory

(cd services/api-gateway     && poetry run dev)   # :8001
(cd services/inference-service && poetry run dev) # :8002
(cd services/geometry-service  && poetry run dev) # :8003
(cd frontend                 && pnpm dev)         # :3000
```

`bash scripts/e2e-smoke.sh` boots all three services and drives one full simulation
against that Postgres. SQLite appears only inside `services/api-gateway/tests`, so the
suite needs no database server.

`API_GATEWAY_URL=http://localhost:8001 pnpm dev` is the default; the proxy is defined in
`frontend/next.config.ts`, so the browser never learns the gateway origin.

Without `DAPR_HTTP_ENDPOINT`, `libs/byb-common/src/byb_common/dapr.py` routes calls
straight to each service URL. Set it to the sidecar (`http://127.0.0.1:3500`) and the
same code publishes to the Dapr topics instead.

Only pub/sub is configured as a Dapr component. Rows are written by SQLAlchemy, so
there is no Dapr state store to keep in sync (and daprd 1.18 no longer bundles
`state.postgresql.postgres`, which would crash-loop every sidecar).

## Poetry commands

| Where | Command | Does |
| --- | --- | --- |
| any service | `poetry install` | deps, incl. the editable `byb-common` path dep |
| any service | `poetry run dev` | uvicorn with reload |
| any service | `poetry run start` | single worker, what the container runs |
| any service | `poetry run test` | that service's pytest suite |
| repo root | `make test` | all three suites |
| repo root | `make lint` | ruff over all three |

Needs Poetry 2.x: metadata lives in the PEP 621 `[project]` table while the
path dependency stays in `[tool.poetry.dependencies]`, which 1.8 rejects. The
images add `--no-root` because the dependency layer is built before `src/` exists.

## API

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/healthz` | per service; reports `dapr` or `http` transport |
| `POST` | `/api/v1/simulations` | `multipart/form-data`: `link` and/or `file`, `room_width_m`, `room_depth_m`, `room_height_m`, `shopper_notes` |
| `GET` | `/api/v1/simulations/{id}` | status, `product_profile`, `fit_report` |
| `GET` | `/api/v1/simulations` | recent jobs |
| `POST` | `/api/v1/internal/results` | worker callback, needs `x-byb-token` |
| `POST` | `/v1/enrich` · `/events` | inference-service sync and subscription entry points |
| `POST` | `/v1/measure` · `/events` | geometry-service sync and subscription entry points |

## Data model

`services/api-gateway/src/byb_gateway/models.py`

- **simulations** — id, status (`pending → enriching → measuring → completed/failed`),
  product link, stored image key, shopper notes, room W/D/H, attempts, error, timestamps
- **simulation_results** — id, simulation FK, `product_profile` JSON, `fit_report` JSON,
  duration. Created by `docker compose up`; `Base.metadata.create_all` runs at startup.

## The fit rules

`services/geometry-service/src/byb_geometry/layout.py`

A face may sit flush against a wall; every face not touching a wall must keep
`max(clearance_cm, MIN_WALKWAY_M)` metres free. The door's quarter-circle sweep on the
front wall stays furniture-free. Verdicts: `fits`, `tight`, `blocked`, `too_large`.
Candidate spots (back wall, both side walls, corner, freestanding, in both orientations)
are all returned so the UI can show alternatives.

## vLLM on AMD

`inference-service` calls an OpenAI-compatible endpoint (`VLLM_BASE_URL`, default
`http://vllm:8000/v1`). The compose `gpu` profile runs `vllm/vllm-openai-rocm` with
`/dev/kfd` and `/dev/dri` passed through — that needs an AMD MI-series host, so on a
laptop leave the profile off. Set `VLLM_MODEL` to a vision model and
`VLLM_SUPPORTS_VISION=true` to feed the uploaded room photo to the model as well.

When no endpoint answers, `products.fallback_profile` returns category heuristics tagged
`source="heuristic"` with `confidence=0.25`, and the UI badge says so. Nothing in the
demo path depends on a GPU.

## Notes

- Uploads land in the `uploads` volume, shared by the gateway and inference services.
- `INTERNAL_TOKEN` guards the worker callback — change it before deploying anywhere.
- CORS allows `http://localhost:3000` and `http://frontend:3000`; add your origin via
  `ALLOWED_ORIGINS` if you deploy the UI elsewhere.
- `daprio/daprd:latest` is unpinned; pin it before production use.
