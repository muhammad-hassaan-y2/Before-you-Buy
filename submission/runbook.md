# Buy You Before — submission runbook

The deadline is **Saturday 2026-10-18, 10:00 UTC**. Lablab closes the submission form then, and the
judging that follows cannot be helped by a late upload. This is the order to do things in, with the
checkpoint that proves each step actually worked rather than just ran without complaining.

Two rules hold throughout: **nothing secret is ever committed** — every value lives in `.env`, and
`.env.example` documents the name only — and **the demo has to survive someone else's network**,
which means the live URL is tested from an incognito window, not the tab that set it up.

---

## 1. Freeze the code (do first, everything else depends on it)

| Check | Command | Proves |
| --- | --- | --- |
| Services | `make test` | seven pytest suites green |
| Front end units | `(cd frontend && pnpm test)` | client, engine maths and panels |
| Front end in a browser | `(cd frontend && pnpm test:e2e)` | both pages driven by Playwright, no backend needed |
| Types and build | `(cd frontend && pnpm build)` | the build the images use |
| The gate | `make eval` | labels re-derived by the geometry service, then the agent scored: 15/15 briefs, 15/15 decisions, **0 false fits** |
| One real journey | `bash scripts/e2e-smoke.sh` | a full simulation and a full agent journey against running services |

`make eval` failing on false fits is a stop, not a footnote — it is the claim the pitch is built on.
Do it before recording, so the number said in the video is the number on screen.

## 2. Bring the stack up

Docker Desktop has to be genuinely alive, not just installed: `docker version` must answer. If it
hangs, restart the daemon — a dead one squats on 8001–8006 with proxies that accept connections and
answer nothing, which looks like a broken service and is not.

```bash
cp .env.example .env      # then edit; never commit this file
docker compose up --build -d
docker compose ps         # every service healthy
```

Sanity from the outside:

```bash
curl -s localhost:8001/api/v1/health
curl -s localhost:8007/agent/tools | head -c 400     # twelve capabilities
```

No GPU is required — `PROFILE` stays unset and the agent falls back to its own heuristics.

## 3. The AMD layer

Run `scripts/prove-amd-vllm.ps1` (or `scripts/amd-vllm-smoke.ps1`) against the droplet and keep the
output. What has to be visible is an OpenAI-compatible `/v1/chat/completions` answer coming from a
model served on AMD hardware through vLLM, with `VLLM_BASE_URL` and `VLLM_MODEL` set from the Token
Factory UI — not invented hostnames.

Then confirm the two consequences:

- `EVOLUS_API_KEY` set and `NEXT_PUBLIC_EVOLUS_*` unset → **no widget loads**; the browser must
  never be given the key.
- The workspace points at the AMD endpoint, so reading the brief and writing the reply cost no
  Evolus credits. Say this in the video; show the model id, not the key.

## 4. The Evolus workspace (the track rule lives here)

The rule is at least two building blocks; we use five, and each needs creating by hand once:

1. **MCP connector** — point it at `PUBLIC_BASE_URL` + `/mcp/`. Check the twelve tools appear in
   the workspace's tool list.
2. **REST API** — one workflow step calling `/agent/tools/simulate_product`. Check it returns
   `{tool, result}`.
3. **Workflow** — the conditional branch (recommend versus hand off), the parallel fits, and the
   loop boundary at the widened budget. Save the id into `EVOLUS_WORKFLOW_ID`.
4. **Knowledge library** — upload the catalog as documents; the agent retrieves from it. Save the id
   into `EVOLUS_LIBRARY_ID`.
5. **Chat widget** — set `NEXT_PUBLIC_EVOLUS_WIDGET_URL` and `..._SCRIPT`, reload `/room-simulator`
   and confirm the panel appears. Leave both blank for a take without it.

Set `EVOLUS_AGENT_ID`, `PUBLIC_BASE_URL`, and change `INTERNAL_TOKEN` from its documented
placeholder. `POST /agent/webhook` has to be reachable from Evolus, so if `PUBLIC_BASE_URL` is
empty the workflow cannot call back — that is the failure mode, and it is silent.

## 5. A URL a judge can open

Expose the frontend and set `PUBLIC_BASE_URL` to the **same** origin the browser uses, or the
connector and the callback both miss.

- Fastest: a tunnel (`cloudflared tunnel --url http://localhost:3000`, or ngrok). Free tiers give a
  random host that changes when the process does — take the video before restarting anything.
- Steadier: a small droplet, `docker compose up -d` there, reverse proxy on 443, TLS. Then
  `ALLOWED_ORIGINS` needs that origin or the browser gets CORS errors that look like a dead app.
- Either way, test from an incognito window on a different network: brief → trace → verdict →
  workspace, and one MCP tool call. If it only works on the machine that runs it, it is not a demo.

Keep the stack warm overnight. One completed simulation on disk means the first judge to open the
page does not watch a cold container start.

## 6. Record

Follow `submission/video-script.md`. Target 5:00, 16:9, 1080p, captions on, no music under the
voice. The load-bearing shot is `fit_report` called over REST returning the same JSON the page read —
it is the evidence that the agent has no private door into the pipeline.

Exports to keep: the video file, one PNG of the trace header with its totals, one PNG of the golden
set scoreboard, and the 16:9 cover (`submission/cover.png`).

## 7. Fill the form

lablab's submission form wants these; have them written before opening it.

| Field | What goes in it |
| --- | --- |
| Title | **Buy You Before — the agent that measures before it recommends** |
| Short description | The one-liner at the bottom of `submission/pitch.md` |
| Full description | Pitch sections 3–7: what it does, the three doors, the delivery path, the golden set |
| Tags | `agents`, `mcp`, `ecommerce`, `computer-vision`, `geometry`, `vllm`, `amd`, `evolus`, `three.js` |
| Prototype URL | the live demo from step 5 |
| Cover image | `submission/cover.png`, 16:9 |
| Demo video | the 5:00 file from step 6 |
| Repo | the GitHub URL, **public**, with the Evolus and AMD sections in the README visible |
| Team | everyone who authored commits — Abeeha Farrukh included |

Before publishing the repo:

```bash
git log --all -- '*.env' '*.env.*'          # nothing but .env.example
git grep -nI -E '(api[_-]?key|token|secret)\s*[:=]\s*["'\'']?[A-Za-z0-9_\-]{12,}' \
  -- ':!*.example' ':!frontend/pnpm-lock.yaml'
```

Any hit is a rotation, not a force-push — the branch has two real authors, so history gets fixed
forward. Add a license, a one-paragraph top of the README, and make sure `.env.example` names every
variable the compose file reads.

## 8. Last hour

- [ ] The demo URL opens in incognito on a phone.
- [ ] The video plays from the platform, not from the file.
- [ ] `make eval` re-run and the scoreboard screenshot matches the number in the video.
- [ ] The repo is public and the README's quick start is copy-pasteable.
- [ ] Nothing in the diff, the screenshots or the recording shows a key.
- [ ] Submitted, with the confirmation saved — and the stack left running for the judging window.

## If something breaks

| Symptom | Almost always | |
| --- | --- | --- |
| Services up, HTTP 500s | Docker's dead port proxy squatting 8001–8006 | restart the daemon, re-run `scripts/e2e-smoke.sh` |
| Journey runs with no Evolus steps | `EVOLUS_API_KEY` unset | the agent answers from its own heuristics — the demo still runs, the track rule does not |
| Workflow never fires | `PUBLIC_BASE_URL` empty or not the origin in the browser | set it, redeploy agent-service |
| Widget missing | `NEXT_PUBLIC_*` unset, or set after the build | both, then rebuild — they are baked in |
| Console shows `could not open WebGL` | GPU-less headless browser | record from a real browser, not a CI one |
| `next dev` serves stale UI during e2e | a leftover dev server holding 3000 that `reuseExistingServer` silently reuses | kill it and let Playwright manage the server |
