# agent-service

The agent layer. It gives an outside agent the ability to act on this shop: search the
catalog, measure a product against a real room, sweep the catalog against that room, widen the
search when nothing fits, explain a verdict in words, price the purchase, hold a piece on the
shopper's own word, and hand the case to a person when it should.

One set of capabilities, reachable through several doors:

| Door | For | Purpose |
| --- | --- | --- |
| `/mcp/` | ChatGPT, Claude, Claude Code, Cursor, the Evolus connector | the tools, resources and prompts the agent attaches to |
| `/agent/tools/{name}` | an Evolus workflow step or webhook | the same tools over plain REST |
| `/agent/connect` | a person adding the connector | the URL, the auth it expects and the steps per client |
| `/agent/brief`, `/agent/runs/{id}`, `/agent/chat` | the shop's own UI | start a journey, watch its trace, talk to the agent |
| `/agent/reservations` | the shop | the holds a human agreed to, still waiting on a person |

## The process it runs

`journey.py` is the business flow, and each step lands in the run trace with the tool that
produced it, its duration and its loop pass:

1. `intake` - the shopper's words arrive from the widget, the API or an Evolus workflow.
2. `brief` - the open model on AMD reads them into a category, a price band and a room.
   Heuristics run first and their numbers win: the shopper's own measurements are never
   overwritten by a guess.
3. `shortlist` - catalog candidates are ranked by match, then by the likelihood of fitting.
4. `simulate` - up to `MAX_CANDIDATES` full pipeline runs, `PARALLEL_FITS` at a time.
5. `branch` - if nothing in the shopper's band fits, the search widens one band and loops.
6. `compare` - recommend the best fit, or hand off when nothing clears the room.
7. `reply` - the answer, optionally rewritten by an Evolus AI Tool.

A verdict is only ever what geometry-service reported for the measured room. The agent never
claims a fit it did not test.

The capabilities that go past measuring are held to the same rule. `explain_fit` turns a
report into facts a shopper can read; `joint_fit` judges a set of pieces as one purchase by
adding their footprints and walkways, and says so when it estimated one. `fit_catalog` answers
the question a shopper actually asks a shop - which of *your* pieces fit my room - by measuring a
capped slice of the catalog in parallel and splitting the result into fits, non-fits and
unproven, because a fit that never settled is not a fit. `proven_fit_offer`
raises an offer only over a fit the engine signed, and carries the simulation id so another
agent can verify it. `reserve_fit` re-reads that proof and refuses unless the caller passes the
shopper's own confirmation words - over MCP it first tries to ask the shopper directly, which is
what a session gives the client - and what it writes is a request a person at the shop accepts or
releases, never a charge. `returns_estimate` is arithmetic over assumptions the caller sees and
can override.

## The connector, and what an outside client needs

`/mcp/` is streamable HTTP over one implementation shared with REST, so an agent in ChatGPT and a
workflow step in Evolus get the same verdict from the same numbers. The frontend proxies it, so the
origin that serves the shop's page is the origin a client adds - one tunnel, both doors. What it
announces:

- **Identity** - title, description, icon and instructions. A connector is shown to a human before
  its first tool is called, and the rules a model must not lose are inside the first 512 characters
  of the instructions, which is the part a client is guaranteed to keep.
- **Hints** - every capability that only measures declares `readOnlyHint`, so a client can run it
  without stopping the shopper; the two that act on stock do not.
- **Resources and prompts** - the catalog, one fit report, one journey trace, and two starting
  prompts, so a client can attach the evidence rather than quote a tool call.
- **Absolute links** - offers, model downloads and run polls are printed against `PUBLIC_BASE_URL`,
  because an agent outside this machine can only follow a URL it can reach.

`MCP_CONNECT_TOKEN` puts a bearer gate on the door. It is off by default: ChatGPT and Claude add a
connector with no auth or with OAuth, so a static key only serves Claude Code, Cursor and Evolus.
`MCP_SESSIONS=true` trades one stateless JSON request per call for a real session, which is what
server-initiated requests - asking the shopper before a hold - need. `ALLOWED_ORIGINS` names the
browsers allowed to call this service; the MCP Inspector is in the default so a connector can be
poked without writing a client for it.

## The golden set

`poetry run eval` runs the journey over `evals/golden_briefs.json` - fifteen briefs, each with
the catalog rows it shortlists and the verdict geometry-service gave each box in that room - and
prints a scoreboard. It reads no network: with no Evolus key and no model endpoint, the
heuristics do the reading and the labels do the measuring, so a red run is a judgement that got
worse, not a wire that came loose.

Three numbers are gated: brief accuracy, decision accuracy, and false fits, which must be zero.
The labels themselves are re-derived by `services/geometry-service/tests/test_golden_labels.py`,
so the file is engine output under test rather than a set of opinions someone typed.

## Configuration

| Variable | Meaning |
| --- | --- |
| `GATEWAY_URL`, `CATALOG_URL` | the pipeline this agent drives |
| `EVOLUS_API_KEY`, `EVOLUS_APP_ID` | workspace key and space id; needed for every Evolus call |
| `EVOLUS_AGENT_ID` | the agent that answers chat (`<appId>:<agentId>` on the OpenAI-compatible endpoint) |
| `EVOLUS_WORKFLOW_ID` | business automation started for each run |
| `EVOLUS_LIBRARY_ID` | knowledge library the agent cites |
| `EVOLUS_REPLY_TOOL` | AI Tool that rewrites the reply; empty sends the agent's own wording |
| `VLLM_BASE_URL`, `VLLM_MODEL`, `VLLM_API_KEY` | the open model served on AMD hardware |
| `PUBLIC_BASE_URL` | this service's reachable URL: the workflow `callbackUrl`, the connector's origin, and the base every link an outside agent is handed is built from |
| `MCP_CONNECT_TOKEN` | bearer key an outside MCP client must send; empty leaves the door open |
| `MCP_SESSIONS` | `true` gives clients a real session, which is how a hold asks the shopper in their own app |
| `ALLOWED_ORIGINS` | browsers allowed to call this service; the MCP Inspector is in the default |
| `MAX_CANDIDATES`, `PARALLEL_FITS`, `SETTLE_TIMEOUT_S` | loop and fan-out boundaries |
| `MAX_CATALOG_FITS` | how many pieces one `fit_catalog` sweep may measure - each one is a GPU job |
| `MAX_JOINT_PIECES`, `MAX_JOINT_COVERAGE`, `MIN_WALKWAY_M` | how many pieces a multi-piece verdict may add up, and the room it must leave clear |

Nothing is required to be set. With no Evolus key the run still completes against the
pipeline and the trace says which steps were skipped; with no model endpoint the heuristics
read the brief and the trace says so too.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | which of Evolus, the AMD model and the pipeline are reachable |
| GET | `/agent/tools` | the tool catalogue |
| GET | `/agent/connect` | the connector's install guide: URL, transport, auth, steps per client |
| POST | `/agent/tools/{name}` | invoke one tool |
| POST | `/agent/brief` | start a journey, returns a run id to poll |
| GET | `/agent/runs` / `/agent/runs/{id}` | recent runs, one run's full trace |
| POST | `/agent/webhooks/evolus` | where a workflow puts its result (`?run=<id>`) |
| POST | `/agent/chat` | chat with the agent; Evolus when configured, the AMD model otherwise |
| GET | `/agent/reservations` | the holds a human agreed to, newest first |
| POST | `/mcp/` | MCP over streamable HTTP |

## Poetry

```bash
poetry install
poetry run dev            # :8007
poetry run start
poetry run test
poetry run eval           # score the agent against the golden set
```
