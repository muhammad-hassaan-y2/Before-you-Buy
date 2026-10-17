# Buy You Before — the fit agent

An e-commerce agent that answers the one question that stops a purchase: **will it fit my
room?** A shopper says it in their own words — "three-seater sofa under 900, and I need to
walk past it to the balcony" — and the agent shortlists the catalog, runs a real fit
simulation for every candidate through the same API a shopper's browser uses, and only then
recommends. Every step it took is on screen, including the ones it skipped.

Seven FastAPI services, one Next.js app, Postgres for state, Dapr for the transport, OpenCV
for the room, Shapely for the geometry, vLLM on AMD for product understanding and listing
reading, and Evolus for the agent, its workflows and its widget.

```
                        ┌─ Next.js :3000 ─/agent──> agent-service :8007
                        │                                 │  MCP / REST / webhooks
browser ────────────────┤                                 ▼
                        │                          Evolus + AMD-hosted model
                        └─/api/v1──> api-gateway :8001 ──SQLAlchemy──> Postgres
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

The agent does not get a private door into the pipeline. It posts to
`/api/v1/simulations` and polls `/api/v1/simulations/{id}` exactly like the front page does,
which is what makes a recommendation defensible to a merchant: the fit it reports is the fit
the geometry worker computed, not one a model asserted.

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
services/agent-service/         the agent: MCP connector, REST tools, Evolus client, journeys
frontend/                       Next.js 16 app: /room-simulator (agent) and /workspace (3D)
docker-compose.yml              postgres + redis + 7 services + daprd sidecars + vllm + frontend
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
(cd services/agent-service     && poetry run dev) # :8007, no sidecar needed
(cd frontend                 && pnpm dev)         # :3000
```

`bash scripts/e2e-smoke.sh` boots all seven services and drives one full simulation
and one agent journey against that Postgres. Ports default to 8001-8007 and can be
overridden (`GATEWAY_PORT=8101 VISION_PORT=8105 bash scripts/e2e-smoke.sh`) when something
else holds them — Docker Desktop on Windows is good at holding ports it will not forward.
SQLite appears only inside `services/api-gateway/tests`, so the suite needs no database
server.

`API_GATEWAY_URL=http://localhost:8001 AGENT_SERVICE_URL=http://localhost:8007 pnpm dev` is
the default; both proxies are defined in `frontend/next.config.ts`, so the browser never
learns the gateway origin and never sees the Evolus key.

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
| repo root | `make test` | all seven service suites |
| repo root | `make lint` | ruff over all seven, using `ruff.toml` |
| repo root | `make eval` | the golden set: labels re-derived by geometry, then the agent scored against them |
| `frontend/` | `pnpm test` | Vitest unit tests for the client, the engine maths and the panels |
| `frontend/` | `pnpm test:e2e` | Playwright against `/room-simulator` and `/workspace` |

Needs Poetry 2.x: metadata lives in the PEP 621 `[project]` table while the
path dependency stays in `[tool.poetry.dependencies]`, which 1.8 rejects. The
images add `--no-root` because the dependency layer is built before `src/` exists.

## API

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/healthz` | per service; reports `dapr` or `http` transport |
| `POST` | `/api/v1/simulations` | `multipart/form-data`: `link` and/or `file` (or an earlier `image_key`), `room_width_m`, `room_depth_m`, `room_height_m`, `shopper_notes` |
| `POST` | `/api/v1/uploads` | store a room photo on its own; returns the `image_key` a simulation or an agent call can point at |
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
| `GET` | `/agent/tools` | the capabilities, in the shape an Evolus AI Tool list wants |
| `POST` | `/agent/tools/{name}` | invoke one capability with a JSON body — the endpoint Evolus calls |
| `POST` | `/agent/brief` | start a journey from a shopper's words, returns a run id to poll |
| `GET` | `/agent/runs` · `/agent/runs/{id}` | the trace: every step, its driver, its duration, the decision |
| `POST` | `/agent/chat` | talk to the Evolus agent, or to the AMD model when Evolus is not configured |
| `POST` | `/agent/webhooks/evolus?run={id}` | where an Evolus workflow puts its result |
| `GET` | `/agent/connect` | how to add the connector to ChatGPT, Claude, Claude Code, Cursor or Evolus |
| `GET` | `/agent/reservations` | the holds the agent took, waiting on a person at the shop |
| `POST` | `/mcp/` | the same capabilities as an MCP connector (streamable HTTP; stateless JSON, or sessions) |

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

A second pass asks the delivery questions the floor plan cannot answer on its own: whether the
box clears the doorway it has to be carried through (tilting included), whether a walkable route
from the door survives at the required clearance, how much floor the placement seals off, and
whether the verdict still holds if every number is off by the survey tolerance. Those come back
as `door_pass`, `walkway_connected`, `isolated_pockets`, `fragile` and `tolerance_cm`. Only one
of them overrides the verdict — a piece that cannot be carried in is not a fit, whatever the
floor area says — and the rest are reported beside it for the agent to weigh.

## Reading the room photo

`services/vision-service/src/byb_vision/photo.py`

OpenCV looks for the vertical wall-to-wall corner and the two wall/floor junctions. The
corner spans floor to ceiling, so its pixel length is the ruler the two wall lengths are
measured with; dark rectangles in the floor band are projected into the room as obstacles.
Nothing is claimed when the photo will not read: the shopper's own dimensions are
forwarded and `room_scan.method` says which of `photo`, `photo-ignored` or `declared` the
run ended up with, which is what the UI badge shows. Ceiling height is never guessed from
a photo — pixels cannot express a dimension the camera never saw.

The key the gateway returns is what the agent tools take (`image_key` on `simulate_product`,
`joint_fit`, `find_alternatives` and `start_journey`), so one photo measures the room once and
every candidate in the journey is fitted into that room instead of the typed numbers. It is the
shopper's *room*, never product evidence: inference-service reads a listing from the page alone
and is not given the picture.

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

Two services use a model, and both speak to one OpenAI-compatible endpoint:
`inference-service` reads product listings for dimensions, `agent-service` uses the same
endpoint for brief reading, replies and the fallback chat. Both read `VLLM_BASE_URL`
(default `http://vllm:8000/v1`), `VLLM_MODEL` and `VLLM_API_KEY`.

The compose `gpu` profile runs `vllm/vllm-openai-rocm` with `/dev/kfd` and `/dev/dri`
passed through — that needs an AMD MI-series host, so on a laptop leave the profile off.
The uploaded photo is the shopper's *room*: vision-service measures it and the product read
never sees it, because a room picture is not evidence about a sofa.

On an AMD Developer Cloud droplet (MI300X) the serving line is:

```bash
docker run --rm --network host --device=/dev/kfd --device=/dev/dri --group-add video \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai-rocm:latest \
  --model Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 8000 \
  --dtype float16 --max-model-len 16384 \
  --api-key "$VLLM_API_KEY" --tool-call-parser hermes
```

`--api-key` because an exposed endpoint would otherwise be open to the internet, and
`--tool-call-parser hermes` because that is what makes Qwen's function calling legible to
vLLM — without it the Evolus agent's tool calls come back as prose. Point the Evolus
workspace at `https://<droplet>:8000/v1` and its own OpenAI-compatible chat surface at
`/v1/chat/completions`; calls to your model do not spend workspace credits.

When no endpoint answers, `products.fallback_profile` returns category heuristics tagged
`source="heuristic"` with `confidence=0.25`, and the UI badge says so. Nothing in the demo
path depends on a GPU, and nothing in the agent path pretends a model spoke when it did not:
each step records its own driver.

## The agent, and the Evolus building blocks it uses

`agent-service` is one FastAPI app with several doors and no privileged path into the
pipeline:

| Door | Shape | Used by |
| --- | --- | --- |
| MCP connector | `/mcp/` — streamable HTTP; stateless JSON by default, real sessions on request | ChatGPT, Claude, Cursor, the Evolus agent |
| REST tools | `/agent/tools`, `/agent/tools/{name}` | an Evolus workflow step or AI Tool |
| Install guide | `/agent/connect` | the shop's page, and a person adding the connector |
| Webhook | `/agent/webhooks/evolus?run={id}` | a workflow putting its result back |
| Shop UI | `/agent/brief`, `/agent/runs`, `/agent/chat` | the Next.js page, proxied so keys stay server-side |
| Holds | `/agent/reservations` | the shop's own queue of holds a human agreed to |

Thirteen capabilities, one implementation behind every door. Measuring: `catalog_search`,
`read_brief`, `simulate_product`, `fit_report`, `explain_fit`, `joint_fit`, `find_alternatives`,
`fit_catalog`. Deciding: `start_journey`, `journey_status`. Acting and costing:
`proven_fit_offer`, `reserve_fit`, `returns_estimate`. A foreseeable failure (unknown SKU, an
unproven piece, a hold without a yes) is reported to the model in words, not as a crash. The five
that measure a room — `simulate_product`, `joint_fit`, `find_alternatives`, `fit_catalog`,
`start_journey` — take an `image_key`, so an external agent fits into the shopper's photographed
room exactly as the shop's own page does.

The three that carry the commerce are deliberately conservative. An **offer** can only be
raised over a fit the geometry engine signed; a **hold** re-reads that proof and refuses unless
the caller passes the shopper's own confirmation words, and what it writes is a request a
person at the shop accepts or releases - nothing is charged and nothing ships. The business
number is arithmetic over assumptions the caller can see and override, never a model's guess.

Five Evolus building blocks are in play: the **custom MCP server**, **custom REST
endpoints/webhooks**, a **workflow** with a conditional branch (recommend vs. handoff), a
parallel fan-out (two fits at a time) and a loop boundary (a widened budget is pass two), the
**knowledge library** the catalog is uploaded to, and the **chat widget** embedded in the
front end as one script tag.

A journey is the auditable unit. `GET /agent/runs/{id}` returns the trace the UI draws:
intake → agent → brief → (room) → shortlist → parallel fits → branch → compare → reply, each with
its `tool`, `ms`, `group` and `iteration`. The `room` step only appears when the brief carried an
`image_key`: the photo is measured first and every candidate after it is fitted into that room.
If the geometry worker never produced a verdict, the agent hands the shopper to a person rather
than inventing one.

### How good is it?

`evals/golden_briefs.json` is fifteen shopper briefs, the catalog rows each one shortlists, and
the verdict geometry-service gave each of those boxes in each of those rooms - 38 verdicts in
all. Two CI steps keep that file honest: geometry-service re-derives every verdict from the
engine, so a label cannot quietly rot into an opinion, and agent-service is then scored against
the labels through the real journey.

`make eval` prints the scoreboard, and the same gate runs as a test. Today: 15/15 briefs read as
written, 15/15 decisions as the labels say, and **0 false fits** among 13 recommendations - the
only number that matters for a product whose whole promise is a fit claim a merchant can stand
behind, because a false "it fits" is precisely the return the demo exists to prevent. The set is
deliberately built around the ways an agent can be wrong, not only right: a piece that sits on
the floor but cannot get through the door, a brief vague enough to spend nothing on, a room
where nothing fits and the search has to widen and still hand off, and a shopper who wrote the
room in centimetres.

### Setting up the Evolus workspace

```bash
EVOLUS_BASE_URL=https://api.evolus.ai/api/v1
EVOLUS_API_KEY=...            # workspace key, never committed
EVOLUS_APP_ID=...             # X-Application-Id
EVOLUS_AGENT_ID=...           # agent id for <app>:<agent> model calls
EVOLUS_WORKFLOW_ID=...        # fit-assurance workflow: branch + parallel fits
EVOLUS_LIBRARY_ID=...         # knowledge library the catalog is uploaded to
PUBLIC_BASE_URL=https://<tunnel>   # so callbackUrl and /mcp/ reach us
```

1. Create the workspace, connect the AMD-hosted model endpoint (base URL + API key). Add an
   agent and note its id.
2. Add a **knowledge library** and upload the catalog: `POST /api/v1/memories/{libraryId}/documents`.
   `poetry -C services/agent-service run python -m byb_agent.evolus_seed` does it from the
   same 36 SKUs the catalog service serves.
3. Build the **workflow**: input = shopper brief, a parallel step that calls
   `POST /agent/tools/simulate_product` per candidate, a conditional branch on the verdict,
   and a webhook out to `{PUBLIC_BASE_URL}/agent/webhooks/evolus?run={id}`. The REST call is
   `multipart` — `input`, `parameters` (JSON string) and `callbackUrl` — and Evolus returns
   `202 { executionId, jobId, traceId }`.
4. Register the **MCP connector** at `{PUBLIC_BASE_URL}/mcp/`. Set `PUBLIC_BASE_URL` to the
   tunnel host: the connector turns on DNS-rebinding protection when it knows its own origin,
   and a foreign `Origin` is then refused with `403`.
5. Copy the **widget** snippet into `NEXT_PUBLIC_EVOLUS_WIDGET_URL` and it appears on every
   page. With the variable empty the page renders no widget, which is what a local clone does.

Without `EVOLUS_API_KEY` the service degrades on purpose: briefs are read by the shipped
heuristics, replies are written from the fit report, and `answered_by` in `/agent/chat` says
which of the two spoke.

### Adding the connector to ChatGPT or Claude

The same `/mcp/` door is what an outside assistant adds, so a shopper can ask their own agent
"which of this shop's sofas fit my 3.6 × 3 m room?" and get a measured answer. `GET /agent/connect`
describes the deployment to the page — the URL, the transport, the auth it actually expects and the
steps per client — because the honest answer differs by client and by environment:

- **It has to be reachable over https.** `PUBLIC_BASE_URL` is what turns a laptop into a connector;
  with it unset, every URL the guide prints is local and no outside assistant can add it. The page
  proxies `/mcp/` to agent-service, so the one tunnel that exposes the shop also exposes its connector.
- **Each panel is named, per client.** ChatGPT hides custom apps behind Developer mode (Settings →
  Security, or Workspace settings → Permissions & roles) and then Apps directory → Advanced → Add
  custom MCP server; claude.ai adds it under Customize → Connectors → + → Add custom connector, with
  an OAuth client id in that dialog's Advanced settings. Claude's Team and Enterprise plans can have
  custom connectors held shut until an admin allows them, which is a shop-side setting, not a bug in
  the connector.
- **Authentication is none or OAuth.** ChatGPT and Claude's app offer those two. A static bearer
  key (`MCP_CONNECT_TOKEN`) is a Claude Code and Cursor thing, so the gate stays off by default and
  the guide says which doors a key locks. What a key is for is a stranger's agent spending the
  merchant's GPU jobs.
- **Tools announce what they do.** Everything that only measures says `readOnlyHint: true`, so a
  client can run it without stopping the human; `proven_fit_offer` and `reserve_fit` do not, and
  nothing is marked destructive. The rules the model must not lose are inside the connector's first
  512 characters of instructions, because that is the part a client is guaranteed to keep.
- **A hold is put to the shopper when the client can ask.** `reserve_fit` tries an elicitation
  first: the shopper answers in the client's own form and those words are what the gate checks.
  That needs a real session, so it comes with `MCP_SESSIONS=true`; otherwise the tool falls back to
  the confirmation the agent relayed — and still refuses a yes it would have to guess at.
- **Evidence travels both ways.** Beside the tools the connector publishes the catalog, one fit
  report and one journey trace as resources, and two prompts a shopper can start from, so a client
  that reads resources quotes the file the engine wrote instead of its own earlier tool call.

Without a public origin the connector still answers locally — that is what the tests and the MCP
Inspector exercise — and the guide simply admits it has no address to hand out.

## The shop's own UI

Two pages, both fed only through the proxies in `frontend/next.config.ts` — the browser
never learns the gateway origin and never sees the Evolus key.

`/room-simulator` is the agent-first page. A shopper writes their brief in their own words;
the panel then shows what the agent heard (category, band, budget, must-haves, and *which
reader* produced it), the trace of the journey with each step's driver and duration, parallel
fan-out marked as such, loop passes as "Pass 2", the verdict for every tested piece with its
tightest walkway, and the reply. The trace totals itself at the top — measured time, how many
pieces the geometry worker actually checked, how many calls went to a model, and the Evolus
execution id when one took part — so the spend sits next to the answer rather than under it.
Below it, the classic single-piece simulator, and a chat panel that names which brain answered.
The brief panel takes a photo of the room as well as the typed numbers: the browser stores it with
the gateway, hands the agent the key it gets back, and every candidate is then measured against the
room in the photo. The trace records that as its own step, and the recommendation opens in the room
that photo measured.

The page ends on the merchant's side of the same journey: what a fit check is worth, recalculated
by `returns_estimate` from assumptions the reviewer can change, and the holds the agent took only
after a shopper said yes in their own words, each linking back to the simulation that proved it.

`/workspace` is the 3D one: pick a SKU off the shelf, give it a room, and stand it there with
three.js — floor, walls, the obstacles vision-service found, the door's quarter-circle sweep,
the product as the part boxes `byb-common` builds for its category, and the clearance
envelope the geometry worker insisted on. Views are the presets scene-service chose, the
placement buttons are the fit report's own candidates, and the glTF download is the same
document. Under the plan, the delivery path the engine actually checked: whether the box clears
the doorway, whether the entrance stays walkable, how much floor it seals off, and whether the
verdict survives the survey tolerance it was measured at. Where WebGL is missing the viewport
says so and the measured 2D plan stays.

Every published fit gets those two views behind one switch — **2D plan**, the top-down polygons the
engine solved, and **3D room**, the same placement stood at scale — and the 3D option is only
offered when a scene was actually built for that run. The workspace opens in the room; the shop's
simulator and the agent's recommendation open on the plan. All three take the room from
`room_scan`, so a photo-measured 3.6 × 3 m room is drawn as that room, not as the numbers someone
typed next to the photo.

The Evolus widget is one script tag, loaded only when `NEXT_PUBLIC_EVOLUS_WIDGET_URL` is set.

## Tests

```bash
make test                        # seven pytest suites
(cd frontend && pnpm test)       # Vitest: client, engine maths, panels
(cd frontend && pnpm test:e2e)   # Playwright against both pages
(cd frontend && pnpm build)      # the type check the images are built with
bash scripts/e2e-smoke.sh        # one full simulation and one journey, no Docker
```

`pnpm test:e2e` boots its own `next dev` unless `E2E_BASE_URL` points at a running stack, and
stubs the services it talks to, so a red run means the front end broke rather than the network.

## Hackathon submission checklist

- [x] Public repo: agent tooling, MCP connector, workflow webhook, configs (`docker-compose.yml`, `.env.example`, `components/`) and this README.
- [x] Containerized: `docker compose up --build` runs the whole stack, no GPU required.
- [x] AMD layer: an open model served on ROCm/vLLM and exposed as an OpenAI-compatible endpoint; the workspace points at it, so its calls cost no Evolus credits.
- [x] Five Evolus building blocks: MCP connector, REST endpoints, a workflow with a conditional branch, a parallel step and a loop boundary, the knowledge library, and the chat widget.
- [x] No committed keys: everything lands in `.env`, and `.env.example` documents each name.
- [ ] Live demo URL: expose the stack and set `PUBLIC_BASE_URL` to the same origin, or the workflow callback and the MCP connector will not reach you.
- [ ] Pitch slides and walkthrough video: record `/room-simulator` end to end — brief, trace, verdict — then the same piece in `/workspace`.

`submission/` holds the pitch and the twelve-slide deck built from it, the timed walkthrough script,
the pre-deadline runbook and the 16:9 cover, so the form has something to paste from and the
recording has an order to follow.

## Notes

- Uploads land in the `uploads` volume, shared by the gateway, inference and vision services.
- `INTERNAL_TOKEN` guards the worker callback — change it before deploying anywhere.
- CORS allows `http://localhost:3000` and `http://frontend:3000`; add your origin via
  `ALLOWED_ORIGINS` if you deploy the UI elsewhere.
- `daprio/daprd:latest` is unpinned; pin it before production use.
