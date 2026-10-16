# Buy You Before — the five-minute walkthrough

The spine of this video is the run trace: a brief goes in, a verdict comes out, and everything
between them is named, timed and re-runnable. Every claim below is something the camera can see on
our own pages, and nothing is narrated that is not on screen.

**Target length** 4:55 — the form caps the walkthrough at five minutes and 300 MB, so export at 1080p
and check the file size before uploading, not after. **Aspect** 16:9. **Captions** burned in or a
sidecar `.srt` — judging includes Presentation, and a silent autoplay on a shared screen still has to
land. **No music under the voice**; the typing is the soundtrack.

---

## Before pressing record

1. The stack is up and green: gateway, catalog, inference, vision, geometry, scene, agent, frontend.
2. One simulation has already completed, so the workspace is not waiting on a cold first run.
3. The briefs are typed in a scratch file and pasted. Live typing is for the one that has to look
   spontaneous — the follow-up question in the chat panel.
4. Zoom the browser to 110–125 %, hide bookmarks, use a clean profile, and record the tab only.
5. Do a 30-second take of the trace section and play it back. Small text on a dark canvas is where
   walkthroughs die.

---

## 0:00 – 0:30 · The question, unanswered

**On screen:** the shop's page, empty brief box.

> "Nobody returns a sofa because the colour was wrong. They return it because it did not fit up the
> stairs, or it ate the walkway to the balcony. A listing gives three numbers and a marketing photo,
> and a chatbot asked 'will it fit' will happily say yes. So we built the agent that measures first."

Type nothing yet. Let the sentence about the chatbot saying yes sit for a beat.

## 0:30 – 1:15 · The brief goes in, the trace arrives

**On screen:** `/room-simulator` — the brief box, then *Find what fits*.

Paste:

> *Three-seater linen sofa under 900, and I need to walk past it to the balcony.*

**Narrate the steps as they appear**, not after:

> "That's the whole input. Intake, then the Evolus agent, then the brief it read — sofa, mid band,
> nine hundred, a four-metre room. The shortlist comes off the catalog. Then the fits run in
> parallel, each one a real simulation, each step stamped with the tool or endpoint that drove it
> and how long it took. This header adds itself up: time measured, how many pieces the geometry
> worker checked, how many calls went to a model, and the Evolus execution id for this run."

Point at the widened-budget branch if it fires on the take — it is the honest moment in the video:
the search spent a second pass rather than recommending something that did not clear the walkway.

## 1:15 – 2:00 · The verdict, and the questions behind it

**On screen:** the result card — piece, verdict, walkway numbers, floor used — then the delivery
path under the plan.

> "It recommends the KURA, and this is the part a model cannot fake: the verdict is geometry. Here
> are the walkways it leaves — that is your balcony requirement, measured. Here is the doorway the
> box has to clear, tilted if it has to, and here is whether the verdict survives the two
> centimetres a tape measure is wrong by. A piece that fits the floor but cannot be carried in is
> not a fit, and the report says so."

Hold on the suggested re-measure line for two seconds. Then the reply from the agent, read aloud in
its own words — it quotes the walkway number, not a feeling.

## 2:00 – 2:45 · Stand it in the room

**On screen:** `/workspace` — place the same piece, orbit, then *first-person*.

Two sentences while it loads, then let it breathe:

> "Same piece, same placement, at scale. Overview first — you can see what it does to the route from
> the door. Now at eye height, standing where you would stand."

Move slowly. One orbit, one first-person look, no mouse shaking. If the measured plan under the view
shows obstacles found in the photo, mention it once: "the radiators came out of the photo, not from
me."

## 2:45 – 3:30 · The same agent from the other door

**On screen:** the capability panel on `/room-simulator`, then one tool called over REST with curl
(or the MCP inspector) in a terminal next to the browser.

> "Twelve capabilities, one implementation, three doors: an MCP connector, REST tool endpoints, and
> the pages a shopper uses. Catalog search, read brief, simulate, fit report, explain, joint fit for
> pieces bought together, alternatives no wider than the first pick, the journey, an offer, a hold,
> and the returns arithmetic. That is a commerce surface another agent can shop — not a chat window
> bolted onto a product page."

Call `fit_report` for the simulation id from the earlier run and show the same JSON the page read.
That is the load-bearing shot of the video: the agent has no private door into the pipeline.

## 3:30 – 4:10 · Prove it, do not claim it

**On screen:** the golden-set run in the terminal — labels re-derived by the geometry service, then
the agent scored against them.

> "Fifteen shopper briefs, thirty-eight labels, and every label is recomputed by the geometry
> service itself in CI — a label cannot quietly turn into an opinion. Scored through the real
> journey: briefs read as written fifteen out of fifteen, decisions matching the labels fifteen out
> of fifteen, and zero false fits across thirteen recommendations. Zero false fits is the gate, and
> it fails the build."

Say "thirteen recommendations" plainly. The set deliberately includes a sectional whose footprint
fills half the floor plan and whose doorway pass comes back `blocked` — the candidate the agent has
to look past — and a brief vague enough that the right answer is to spend nothing on it.

## 4:10 – 4:45 · What it is worth, and how it closes

**On screen:** the merchant section at the bottom of `/room-simulator` — the value panel, then the
holds list.

> "The value panel is arithmetic over assumptions a reviewer can change: orders a month, return
> rate, the share of returns that are fit-driven, the share a fit check prevents. Every number is
> the service's own, and the note says band prices stand in until a real price feed is wired. Then
> the close: an offer only a proven fit can back, and a hold that appears only because the shopper
> said yes in their own words — and those words stay on the row. Nothing is charged, nothing ships."

## 4:45 – 4:55 · The one line

**On screen:** the trace header again, or the title card.

> "An e-commerce agent that measures the room, proves the fit with geometry, shows the trace behind
> every recommendation, and is scored against engine-derived labels with a build gate on false fits."

Then a beat of the Evolus workspace — the workflow, the knowledge library with the catalog in it,
the model served on AMD hardware — and cut.

---

## What not to say

- Do not claim the model decides the fit. It reads and replies; the engine measures. That
  separation is the reason the zero-false-fits number means anything.
- Do not call the returns figures the merchant's. They are arithmetic over stated assumptions, and
  the panel says so on screen.
- Do not claim the catalog is the merchant's. It is thirty-six SKUs our catalog service serves,
  which is enough for the agent to shop and not enough to pretend otherwise.
- Do not narrate over the trace. Let the steps arrive on their own timing and talk after them.
- Never show the environment file, the key inputs, or a token on screen. If a terminal is visible,
  the secrets are not.
