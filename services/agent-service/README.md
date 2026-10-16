# agent-service

The agent layer. It gives the Evolus agent the ability to act on this shop: search the
catalog, measure a product against a real room, widen the search when nothing fits, explain a
verdict in words, price the purchase, hold a piece on the shopper's own word, and hand the case
to a person when it should.

One set of capabilities, reachable through several doors:

| Door | For | Purpose |
| --- | --- | --- |
| `/mcp/` | the Evolus MCP connector, Claude Code, Evolus Studio | the tools the agent calls while it reasons |
| `/agent/tools/{name}` | an Evolus workflow step or webhook | the same tools over plain REST |
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
adding their footprints and walkways, and says so when it estimated one. `proven_fit_offer`
raises an offer only over a fit the engine signed, and carries the simulation id so another
agent can verify it. `reserve_fit` re-reads that proof and refuses unless the caller passes the
shopper's own confirmation words - the result is a request a person at the shop accepts or
releases, never a charge. `returns_estimate` is arithmetic over assumptions the caller sees and
can override.

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
| `PUBLIC_BASE_URL` | this service's reachable URL, used as the workflow `callbackUrl` |
| `MAX_CANDIDATES`, `PARALLEL_FITS`, `SETTLE_TIMEOUT_S` | loop and fan-out boundaries |
| `MAX_JOINT_PIECES`, `MAX_JOINT_COVERAGE`, `MIN_WALKWAY_M` | how many pieces a multi-piece verdict may add up, and the room it must leave clear |

Nothing is required to be set. With no Evolus key the run still completes against the
pipeline and the trace says which steps were skipped; with no model endpoint the heuristics
read the brief and the trace says so too.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | which of Evolus, the AMD model and the pipeline are reachable |
| GET | `/agent/tools` | the tool catalogue |
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
```
