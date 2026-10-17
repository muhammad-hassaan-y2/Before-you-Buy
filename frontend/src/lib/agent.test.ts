import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AgentError, chat, fetchReservations, fetchTools, pollRun, returnsEstimate, runCost, startJourney, type AgentRun, type AgentStep } from "@/lib/agent"

afterEach(() => vi.unstubAllGlobals())

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
}

function run(status: AgentRun["status"]): AgentRun {
  return { id: "r1", status, brief: null, steps: [], attempts: [], decision: null, reply: null, evolus_execution_id: null, conversation_id: null, error: null }
}

describe("startJourney", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("posts the brief with nulls for the room and the photo it was not given", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse({ run_id: "r1", status: "running", poll: "/agent/runs/r1" }))
    vi.stubGlobal("fetch", fetch)

    await expect(startJourney({ brief: "a sofa under 900" })).resolves.toMatchObject({ run_id: "r1" })
    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, init] = fetch.mock.calls[0]
    expect(url).toBe("/agent/brief")
    expect(JSON.parse(String(init.body))).toEqual({
      brief: "a sofa under 900",
      room_width_m: null,
      room_depth_m: null,
      room_height_m: null,
      image_key: null,
    })
  })

  it("sends the key of the room photo the shopper attached", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse({ run_id: "r1", status: "running", poll: "/agent/runs/r1" }))
    vi.stubGlobal("fetch", fetch)

    await startJourney({ brief: "will a sofa fit the room in my photo", imageKey: "abc123-living-room.jpg" })
    expect(JSON.parse(String(fetch.mock.calls[0][1].body)).image_key).toBe("abc123-living-room.jpg")
  })

  it("turns a rejected run into a readable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({ detail: "brief is too short" }, 422))))
    await expect(startJourney({ brief: "x" })).rejects.toThrow(AgentError)
    await expect(startJourney({ brief: "x" })).rejects.toThrow("brief is too short")
  })
})

describe("pollRun", () => {
  it("stops as soon as the journey settles and reports every snapshot", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(jsonResponse(run("running"))).mockResolvedValue(jsonResponse(run("done")))
    vi.stubGlobal("fetch", fetch)
    const seen: string[] = []

    const settled = await pollRun("r1", (snapshot) => seen.push(snapshot.status), { intervalMs: 1 })

    expect(seen).toEqual(["running", "done"])
    expect(settled?.status).toBe("done")
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it("hands back the last snapshot when the budget runs out", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(run("running")))))
    const settled = await pollRun("r1", () => {}, { intervalMs: 1, attempts: 3 })
    expect(settled?.status).toBe("running")
  })

  it("stops polling when the caller aborts", async () => {
    const controller = new AbortController()
    const fetch = vi.fn().mockImplementation(async () => {
      controller.abort()
      return jsonResponse(run("running"))
    })
    vi.stubGlobal("fetch", fetch)

    await pollRun("r1", () => {}, { intervalMs: 1, attempts: 10, signal: controller.signal })
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

describe("chat", () => {
  it("carries the conversation id on a header as well as in the body", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse({ answer: "It fits.", answered_by: "evolus", conversation_id: "c2" }))
    vi.stubGlobal("fetch", fetch)

    const reply = await chat([{ role: "user", content: "will it fit?" }], "c1")
    expect(reply.answer).toBe("It fits.")
    const [url, init] = fetch.mock.calls[0]
    expect(url).toBe("/agent/chat")
    expect((init.headers as Record<string, string>)["X-Conversation-Id"]).toBe("c1")
    expect(JSON.parse(String(init.body)).conversation_id).toBe("c1")
  })

  it("says which brain answered so the UI can label it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ answer: "Yes.", answered_by: "Qwen/Qwen2.5-3B-Instruct" })))
    const reply = await chat([{ role: "user", content: "hi" }])
    expect(reply.answered_by).toContain("Qwen")
    expect(reply.conversation_id).toBeUndefined()
  })

  it("is honest about a service with no brain configured", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "neither Evolus nor an AMD model endpoint is configured" }, 503)))
    await expect(chat([{ role: "user", content: "hi" }])).rejects.toThrow("neither Evolus nor an AMD model endpoint is configured")
  })
})

describe("fetchTools", () => {
  it("unwraps the catalog the agent service publishes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ tools: [{ name: "simulate_product", description: "Measure one product." }] })))
    await expect(fetchTools()).resolves.toEqual([{ name: "simulate_product", description: "Measure one product." }])
  })
})

describe("returnsEstimate", () => {
  it("spells the assumptions the way the tool does and unwraps its result", async () => {
    const result = {
      orders_per_month: 2000,
      returns_per_month: 600,
      fit_driven_returns_per_month: 402,
      returns_prevented_per_month: 40.2,
      handling_saved_eur_per_month: 402,
      revenue_kept_eur_per_month: 60300,
      per_simulation_value_eur: 30.35,
      assumptions: {
        return_rate: 0.3,
        fit_driven_share_of_returns: 0.67,
        handling_cost_eur_per_return: 10,
        average_order_value_eur: 1500,
        share_of_fit_returns_prevented: 0.1,
        note: "Band prices stand in for the merchant feed until it is wired.",
      },
    }
    const fetch = vi.fn().mockResolvedValue(jsonResponse({ tool: "returns_estimate", result }))
    vi.stubGlobal("fetch", fetch)

    await expect(returnsEstimate({ ordersPerMonth: 2000, priceBand: "$$$", returnRate: 0.3, prevention: 0.1 })).resolves.toEqual(result)
    const [url, init] = fetch.mock.calls[0]
    expect(url).toBe("/agent/tools/returns_estimate")
    expect(JSON.parse(String(init.body))).toEqual({
      orders_per_month: 2000,
      price_band: "$$$",
      price_eur: null,
      return_rate: 0.3,
      fit_share: null,
      prevention: 0.1,
    })
  })

  it("keeps a refused call readable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "return_rate must be between 0 and 1" }, 422)))
    await expect(returnsEstimate({ returnRate: 3 })).rejects.toThrow(AgentError)
  })
})

describe("fetchReservations", () => {
  it("reads the holds a person still has to accept", async () => {
    const holds = [
      { id: "r1", simulation_id: "s1", sku: "SOFA-302", name: "Ektorp 3-seat sofa", verdict: "fits", confirmation: "yes hold it", status: "pending_merchant", created_at: "2026-10-16T09:00:00Z" },
    ]
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(holds)))
    await expect(fetchReservations(5)).resolves.toEqual(holds)
  })
})

describe("runCost", () => {
  const step = (over: Partial<AgentStep>): AgentStep => ({ index: 0, kind: "fit", status: "ok", detail: "", tool: "geometry-service", group: null, iteration: 1, ms: 100, output: null, ...over })

  it("counts the geometry the worker measured and the calls that went to a model", () => {
    const finished: AgentRun = {
      ...run("done"),
      evolus_execution_id: "exec-9",
      steps: [
        step({ kind: "agent", tool: "POST /v1/chat/completions", ms: 700 }),
        step({ kind: "agent", tool: "POST /v1/chat/completions", status: "skipped", ms: 0 }),
        step({ kind: "brief", tool: "heuristics", ms: 4 }),
        step({ kind: "shortlist", tool: "GET /api/v1/catalog", ms: 21 }),
        step({ kind: "simulate", tool: "POST /api/v1/simulations", ms: 3000 }),
        step({ detail: "SOFA-302 -> fits", ms: 1500, iteration: 2 }),
        step({ detail: "SOFA-401 -> tight", ms: 900, iteration: 2 }),
        step({ kind: "reply", tool: "evolus", ms: 300, iteration: 2 }),
      ],
    }

    expect(runCost(finished)).toMatchObject({ total_ms: 6425, fits: 2, model_calls: 2, passes: 2, slowest: { label: "simulate", ms: 3000 } })
  })

  it("says so when nothing was timed", () => {
    expect(runCost({ ...run("running"), steps: [step({ ms: 0 })] })).toMatchObject({ total_ms: 0, fits: 1, model_calls: 0, passes: 1, slowest: null })
  })
})
