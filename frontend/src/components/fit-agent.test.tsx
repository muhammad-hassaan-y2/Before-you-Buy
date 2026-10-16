import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FitAgent } from "@/components/fit-agent"
import type { AgentRun } from "@/lib/agent"

const run: AgentRun = {
  id: "abc123",
  status: "done",
  brief: {
    raw: "three-seater sofa under 900",
    category: "sofa",
    price_band: "$$",
    budget_eur: 900,
    room_width_m: 4,
    room_depth_m: 3.5,
    room_height_m: 2.4,
    must_haves: ["linen"],
    confidence: 0.7,
    source: "heuristic",
  },
  steps: [
    { index: 0, kind: "intake", status: "ok", detail: "three-seater sofa under 900", tool: null, group: null, iteration: 1, ms: 0, output: null },
    { index: 1, kind: "brief", status: "ok", detail: "sofa · $$ · 900", tool: "heuristics", group: null, iteration: 1, ms: 4, output: null },
    { index: 2, kind: "shortlist", status: "ok", detail: "4 candidates", tool: "GET /api/v1/catalog", group: null, iteration: 1, ms: 21, output: null },
    { index: 3, kind: "simulate", status: "ok", detail: "SKYDD 45 fitted", tool: "POST /api/v1/simulations", group: "fits", iteration: 1, ms: 3200, output: null },
    { index: 4, kind: "branch", status: "ok", detail: "widened the band to $$$", tool: null, group: null, iteration: 2, ms: 0, output: null },
    { index: 5, kind: "reply", status: "ok", detail: "", tool: "evolus", group: null, iteration: 2, ms: 800, output: null },
  ],
  attempts: [
    {
      sku: "SKU-1",
      name: "KURA sofa",
      price_band: "$$",
      score: 0.8,
      simulation_id: "sim-1",
      status: "done",
      verdict: "fits",
      coverage_pct: 14.2,
      walkway_m: { left: 0.9, right: 0.75, front: 0.6, back: 0.2 },
      reason: null,
    },
    { sku: "SKU-2", name: "BILLY shelf", price_band: "$", score: 0.4, simulation_id: null, status: "failed", verdict: null, coverage_pct: 0, walkway_m: {}, reason: "the worker failed" },
  ],
  decision: { action: "recommend", sku: "SKU-1", simulation_id: "sim-1", confidence: 0.82, reason: "widest walkway of the four", evidence: null },
  reply: "The KURA sofa fits with a 0.6 m walkway to the balcony.",
  evolus_execution_id: "exec-9",
  conversation_id: null,
  error: null,
}

function respondingTo(handler: (url: string, init?: RequestInit) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      new Response(JSON.stringify(handler(String(input), init)), { status: 200, headers: { "Content-Type": "application/json" } }),
    ),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe("FitAgent", () => {
  it("starts a journey from the shopper's own words and shows the room it heard", async () => {
    respondingTo((url) => (url === "/agent/brief" ? { run_id: "abc123", status: "running", poll: "/agent/runs/abc123" } : run))
    render(<FitAgent />)

    fireEvent.change(screen.getByLabelText("Your brief"), { target: { value: "a 2 door wardrobe, max 600" } })
    fireEvent.click(screen.getByRole("button", { name: /Find what fits/i }))

    expect(await screen.findByText(/The KURA sofa fits/)).toBeInTheDocument()
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(JSON.parse(String(init.body)).brief).toBe("a 2 door wardrobe, max 600")

    expect(screen.getByText("sofa")).toBeInTheDocument()
    expect(screen.getByText("Read by heuristic · confidence 70 %")).toBeInTheDocument()
  })

  it("renders every step, its driver and its duration", async () => {
    respondingTo(() => run)
    render(<FitAgent />)
    fireEvent.click(screen.getByRole("button", { name: /Find what fits/i }))

    await screen.findByText("Catalog shortlisted")
    expect(screen.getByText("4 candidates")).toBeInTheDocument()
    expect(screen.getByText("GET /api/v1/catalog")).toBeInTheDocument()
    expect(screen.getByText("3200 ms")).toBeInTheDocument()
    expect(screen.getByText(/fits · parallel/)).toBeInTheDocument()
    expect(screen.getByText("Pass 2")).toBeInTheDocument()
  })

  it("marks the recommendation and the evidence behind it", async () => {
    respondingTo(() => run)
    render(<FitAgent />)
    fireEvent.click(screen.getByRole("button", { name: /Find what fits/i }))

    const attempt = await screen.findByText("KURA sofa")
    expect(screen.getByText("fits")).toBeInTheDocument()
    expect(attempt.parentElement).toHaveTextContent("0.20 m walkway")
    expect(screen.getByText("recommend")).toBeInTheDocument()
    expect(screen.getByText("widest walkway of the four")).toBeInTheDocument()
  })

  it("says when a candidate could not be measured instead of hiding it", async () => {
    respondingTo(() => run)
    render(<FitAgent />)
    fireEvent.click(screen.getByRole("button", { name: /Find what fits/i }))

    await waitFor(() => expect(screen.getByText("BILLY shelf")).toBeInTheDocument())
    expect(screen.getByText("failed")).toBeInTheDocument()
  })

  it("hands over to a person when the agent decides not to recommend", async () => {
    respondingTo((url) => (url === "/agent/brief" ? { run_id: "abc123", status: "running" } : { ...run, status: "awaiting_human", decision: { ...run.decision!, action: "handoff", reason: "no candidate cleared the walkway test" } }))
    render(<FitAgent />)
    fireEvent.click(screen.getByRole("button", { name: /Find what fits/i }))

    expect(await screen.findByText(/A person takes it from here/i)).toBeInTheDocument()
    expect(screen.getByText("no candidate cleared the walkway test")).toBeInTheDocument()
    expect(screen.queryByText("recommend")).not.toBeInTheDocument()
  })

  it("refuses to send a brief that says nothing", async () => {
    respondingTo(() => run)
    render(<FitAgent />)
    fireEvent.change(screen.getByLabelText("Your brief"), { target: { value: "  " } })
    fireEvent.click(screen.getByRole("button", { name: /Find what fits/i }))

    expect(await screen.findByText(/Describe what you are looking for/)).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })
})
