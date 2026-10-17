# Buy You Before — pitch

AMD Developer Hackathon: ACT III · Evolus partner track · "Reinvent Commerce"
Four slides of it fit on a screen; twelve in the deck. Judged on Application of Technology,
Presentation, Business Value and Originality, so each section below says which one it is aiming at.

---

## 1. Title

**Buy You Before — the agent that measures before it recommends.**

An e-commerce agent that answers the question that stops the purchase: *will it fit my room?*
It only ever recommends what a geometry engine proved, and it shows the proof.

`Buy your before` · one Next.js app, seven services, one Evolus workspace, one AMD-hosted model.

## 2. The problem — Business Value

- Nobody returns a sofa because the colour was wrong. They return it because it did not fit up
  the stairs, or it ate the walkway to the balcony.
- A shopper cannot tell before ordering. The listing gives three numbers and a marketing photo.
- The merchant pays for that twice: once in the handling of the return, once in the sale they
  did not make because the shopper hesitated and put it back.
- A chatbot fixes none of this. Asked "will it fit", a language model will happily say yes.

## 3. What we built — Originality

A shopper writes what they would say to a shop assistant:

> *Three-seater linen sofa under 900, and I need to walk past it to the balcony.*

The agent reads the brief, shortlists the catalog, and runs a **real fit simulation** for every
candidate through the same API a shopper's browser uses. It recommends only what comes back
fitting, hands the shopper to a person when nothing does, and never invents a verdict.

The agent does not have a private door into the pipeline. The fit it reports is the fit the
geometry worker computed.

## 4. Agent-first, not AI decoration — Application of Technology

Thirteen capabilities, one implementation, three doors:

| Door | Who uses it |
| --- | --- |
| MCP connector | any agent that speaks MCP — Evolus, ChatGPT, Claude, Cursor |
| REST tool endpoints | an Evolus workflow step, a checkout bot, a webhook |
| The shop's own pages | the shopper, and the merchant checking the holds |

`catalog_search · read_brief · simulate_product · fit_report · explain_fit · joint_fit ·
find_alternatives · fit_catalog · start_journey · journey_status · proven_fit_offer · reserve_fit ·
returns_estimate`

An agent that can shop your catalog, measure a room, sweep the catalog against that room, explain a
verdict, judge a set of pieces as one purchase and take a hold — that is a commerce surface, not a
demo chat window. The connector is a real remote one: a shopper adds it to ChatGPT or Claude and
asks which of the shop's sofas fit their 3.6 × 3 m room, and the hold it offers still needs their
own yes, asked in the client's own form when the client has one.

## 5. What the geometry actually decides

The verdict is Shapely, not a token. OpenCV reads the room out of the photo, or the shopper's own
numbers stand. Then the engine answers the questions a listing never asks:

- does the box get through the doorway, tilting included;
- once it is in, is there still a walkable route from the door, or does it seal floor off behind it;
- does the verdict survive the two centimetres every tape measure is wrong by.

A piece that fits the floor plan but cannot be carried in is not a fit, and the report says so.

## 6. The auditable unit — Application of Technology

Every journey records its own trace: intake → agent → brief → shortlist → parallel fits →
branch → compare → reply. Each step names the tool or endpoint that drove it, how long it took,
and which loop pass it belongs to. The header totals itself: time measured, pieces the geometry
worker checked, calls that went to a model, and the Evolus execution id when one took part.

That is the whole argument of the project. A merchant who is asked to trust a recommendation can
re-run the fit the agent ran and read the same trace.

## 7. Prove it, do not claim it — Business Value

A golden set of fifteen shopper briefs, the catalog rows each one shortlists, and the verdict
the engine gave each of those boxes in each of those rooms — thirty-eight labels, all of them
**re-derived in CI by the geometry service itself**, so a label cannot quietly become an opinion.

The agent is then scored against those labels through the real journey:

- briefs read as written: **15 / 15**
- decisions matching the labels: **15 / 15**
- **false fits: 0** across thirteen recommendations — the gate, and it fails the build

The set includes a sectional whose footprint fills half the floor plan and whose doorway pass comes
back `blocked` — the candidate the agent has to look past — a brief vague enough that the right
answer is to spend nothing on it, a room where nothing fits and the search has to widen and still
hand off, and a shopper who wrote their room in centimetres.

## 8. The five Evolus building blocks — Application of Technology

| Block | In this project |
| --- | --- |
| MCP connector | the thirteen capabilities, mounted at `/mcp/` — addable to ChatGPT or Claude |
| REST API | every capability is a POST an Evolus step can call |
| Workflow | conditional branch (recommend vs. hand off), parallel fits, a loop boundary at the widened budget |
| Knowledge library | the catalog, uploaded as documents the agent can retrieve |
| Chat widget | one script tag on the shop's pages |

Bring-your-own-model: the workspace points at an open model served on AMD hardware through vLLM,
so the reading and the replies run there and cost no Evolus credits. The rule that a language
model may not be the only forecasting method is honoured in the architecture, not in a footnote:
the model reads, the engine measures, the arithmetic over stated assumptions prices it.

## 9. What it is worth to the shop

`returns_estimate` answers in arithmetic over assumptions a reviewer can change: orders a month,
return rate, the share of returns that are fit-driven, the share a fit check prevents, handling
cost, average order value. Every figure on that panel is the service's own, and the note says
plainly that band prices stand in until the merchant's price feed is wired.

The close is human-gated. `proven_fit_offer` turns a proven fit into an offer another agent or a
checkout can act on; `reserve_fit` takes a hold **only** after the shopper says yes in their own
words, and the holds page keeps those words with the hold. Nothing is charged and nothing ships
from this service.

## 10. Demo — Presentation

Ninety seconds of typing, ninety of the trace, the rest of the proof:

1. type the brief, watch the steps arrive with their driver and duration;
2. read the verdict: the piece, the walkway it leaves, the doorway it has to clear;
3. stand it in the room at eye height in the 3D workspace;
4. show the same capability list from the MCP door — the agent's tools, unchanged;
5. open the golden set scoreboard: 15/15, 15/15, 0 false fits;
6. end on the merchant's numbers and the hold waiting for a person.

## 11. Why this could win

- The hard part is real and already done: a deterministic fit engine with a delivery path, not a
  wrapper around a chat model.
- The agent is measured, with the measurement in CI and a gate that fails the build.
- It is a commerce surface a merchant could be handed: capabilities, offers, holds, a number.
- It uses the partner's blocks the way they are meant to be used — and the model runs on AMD.

## 12. Where it goes next

- the merchant's real price feed, replacing the band prices the estimate states it stands in for;
- multi-piece layout search, so `joint_fit` stops adding footprints and starts arranging them;
- catalog ingestion beyond the thirty-six SKUs, and a doorway survey from the same photo;
- an offer that a checkout can complete, with the hold as the human gate it already is.

---

### One line for the submission form

An e-commerce agent that measures a room, proves a fit with geometry, shows the trace behind every
recommendation, and is scored against thirty-eight engine-derived labels with a build gate on
false fits — because a model that guesses whether a sofa fits is the reason returns exist.
