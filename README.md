# Buy You Before — Room Simulator

Check whether a piece of furniture actually fits your room **before** you buy it.
Paste a product link (or upload a room photo), and the stack works out the item's real
dimensions and tests its footprint against your walls, door swing and walkway.

Six FastAPI services, one Next.js app, Postgres for state, Dapr for the transport,
OpenCV for the room and vLLM (AMD ROCm) for product understanding.

```
browser ──> Next.js :3000 ──/api/v1──> api-gateway :8001 ──SQLAlchemy──> Postgres
                                            │  simulation.requested (Dapr pub/sub)
                                            ▼
                                     catalog-service :8004 ──SKU match──> candidate
                                            │  simulation.catalogued
                                            ▼
                                     inference-service :8002 ──HTTP──> vLLM (ROCm)
                                            │  simulation.measured
                                            ▼
                                     vision-service :8005 ──OpenCV──> room + obstacles
                                            │  simulation.room_scanned
                                            ▼
                                     geometry-service :8003 ──Shapely──> fit report
                                            │  simulation.fitted
                                            ▼
                                     scene-service :8006 ──SceneSpec + glTF 2.0
                                            │  POST /api/v1/internal/results
                                            ▼
                                       api-gateway (persists, browser polls)
```

Each hop also posts to `/api/v1/internal/progress`, which is what moves the step
indicator in the UI while the chain is running.

## Layout

```
components/                     Dapr components (Redis pub/sub)
libs/byb-common/                shared event contracts, part builders + Dapr transport shim
services/api-gateway/           FastAPI, SQLAlchemy models, ingest and job state
services/catalog-service/       seeded furniture catalog, link/notes -> SKU
services/inference-service/     vLLM product dimensions, catalog prior, heuristic fallback
services/vision-service/        OpenCV room photo -> dimensions and floor obstacles
services/geometry-service/      Shapely fit analysis and placement candidates
services/scene-service/         SceneSpec + glTF 2.0 document for the 3D view and download
frontend/                       Next.js 16 app, page at /room-simulator
docker-compose.yml              postgres + redis + 6 services + 6 daprd + vllm + frontend
ruff.toml                       one lint config for every Poetry project
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
(cd services/catalog-service && poetry run dev)   # :8004
(cd services/inference-service && poetry run dev) # :8002
(cd services/vision-service  && poetry run dev)   # :8005
(cd services/geometry-service  && poetry run dev) # :8003
(cd services/scene-service     && poetry run dev) # :8006
(cd frontend                 && pnpm dev)         # :3000
```

`bash scripts/e2e-smoke.sh` boots all six services and drives one full simulation
against that Postgres. Ports default to 8001-8006 and can be overridden
(`GATEWAY_PORT=8101 VISION_PORT=8105 bash scripts/e2e-smoke.sh`) when something else
holds them — Docker Desktop on Windows is good at holding ports it will not forward.
SQLite appears only inside `services/api-gateway/tests`, so the suite needs no database
server.

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
| repo root | `make test` | all six service suites |
| repo root | `make lint` | ruff over all six, using `ruff.toml` |

Needs Poetry 2.x: metadata lives in the PEP 621 `[project]` table while the
path dependency stays in `[tool.poetry.dependencies]`, which 1.8 rejects. The
images add `--no-root` because the dependency layer is built before `src/` exists.

## API

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/healthz` | per service; reports `dapr` or `http` transport |
| `POST` | `/api/v1/simulations` | `multipart/form-data`: `link` and/or `file`, `room_width_m`, `room_depth_m`, `room_height_m`, `shopper_notes` |
| `GET` | `/api/v1/simulations/{id}` | status, `catalog_candidate`, `product_profile`, `room_scan`, `fit_report`, `scene`, `has_model` |
| `GET` | `/api/v1/simulations/{id}/model` | the glTF 2.0 document, served as a download on demand |
| `GET` | `/api/v1/simulations` | recent jobs |
| `GET` | `/api/v1/catalog` | gateway proxy of catalog-service's SKU list |
| `POST` | `/api/v1/internal/results` | worker callback, needs `x-byb-token` |
| `POST` | `/api/v1/internal/progress` | stage report, needs `x-byb-token`, ignored once settled |
| `POST` | `/v1/catalogue` · `/events` | catalog-service sync and subscription entry points |
| `POST` | `/v1/enrich` · `/events` | inference-service sync and subscription entry points |
| `POST` | `/v1/scan` · `/events` | vision-service sync and subscription entry points |
| `POST` | `/v1/fit` · `/events` | geometry-service sync and subscription entry points |
| `POST` | `/v1/render` · `/events` | scene-service sync and subscription entry points |

## Data model

`services/api-gateway/src/byb_gateway/models.py`

- **simulations** — id, status (`pending → cataloguing → enriching → measuring → scanning →
  fitting → rendering → completed/failed`), product link, stored image key, shopper notes,
  room W/D/H, attempts, error, timestamps
- **simulation_results** — id, simulation FK, `catalog_candidate`, `product_profile`,
  `room_scan`, `fit_report`, `scene_spec` and `model_gltf` as JSON, duration. Created by
  `docker compose up`; `Base.metadata.create_all` runs at startup and
  `_add_missing_columns()` then ALTERs in any column the model gained since that volume was
  created.

## The fit rules

`services/geometry-service/src/byb_geometry/layout.py`

A face may sit flush against a wall; every face not touching a wall must keep
`max(clearance_cm, MIN_WALKWAY_M)` metres free. The door's quarter-circle sweep on the
front wall stays furniture-free, and so does whatever vision-service found on the floor.
Verdicts: `fits`, `tight`, `blocked`, `too_large`. Candidate spots (back wall, both side
walls, corner, freestanding, in both orientations) are all returned with their centre,
orientation and four walkway gaps, so the UI can show alternatives and draw them.

## Reading the room photo

`services/vision-service/src/byb_vision/photo.py`

OpenCV looks for the vertical wall-to-wall corner and the two wall/floor junctions. The
corner spans floor to ceiling, so its pixel length is the ruler the two wall lengths are
measured with; dark rectangles in the floor band are projected into the room as obstacles.
Nothing is claimed when the photo will not read: the shopper's own dimensions are
forwarded and `room_scan.method` says which of `photo`, `photo-ignored` or `declared` the
run ended up with, which is what the UI badge shows. Ceiling height is never guessed from
a photo — pixels cannot express a dimension the camera never saw.

## The 3D scene and the download

`services/scene-service`

Scene-service is the only worker that closes a simulation, so "it is finished" stays a
single decision instead of a race between callbacks. It restates the fit report as a
`SceneSpec` — room shell, door swing, obstacle volumes, the product as the part boxes
`byb-common` builds for its category, one transform per candidate spot, three camera
presets — in the same room-local metres the fit analysis already used, so the 3D view and
the verdict cannot describe different rooms.

It also writes a glTF 2.0 document: one unit cube in the buffer, every box a node with a
scale, self-contained through a base64 buffer so the file opens in any viewer without
companions. It travels inside the result callback and is stored with the simulation, then
served on demand — the polling payload only carries `has_model`.

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

- Uploads land in the `uploads` volume, shared by the gateway, inference and vision services.
- `INTERNAL_TOKEN` guards the worker callback — change it before deploying anywhere.
- CORS allows `http://localhost:3000` and `http://frontend:3000`; add your origin via
  `ALLOWED_ORIGINS` if you deploy the UI elsewhere.
- `daprio/daprd:latest` is unpinned; pin it before production use.
