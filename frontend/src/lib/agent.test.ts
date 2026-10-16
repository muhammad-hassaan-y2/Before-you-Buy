import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AgentError, chat, fetchTools, pollRun, startJourney, type AgentRun } from "@/lib/agent"

afterEach(() => vi.unstubAllGlobals())

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
}

function run(status: AgentRun["status"]): AgentRun {
  return { id: "r1", status, brief: null, steps: [], attempts: [], decision: null, reply: null, evolus_execution_id: null, conversation_id: null, error: null }
}

describe("startJourney", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("posts the brief with nulls for the room it was not given", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse({ run_id: "r1", status: "running", poll: "/agent/runs/r1" }))
    vi.stubGlobal("fetch", fetch)

    await expect(startJourney({ brief: "a sofa under 900" })).resolves.toMatchObject({ run_id: "r1" })
    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, init] = fetch.mock.calls[0]
    expect(url).toBe("/agent/brief")
    expect(JSON.parse(String(init.body))).toEqual({ brief: "a sofa under 900", room_width_m: null, room_depth_m: null, room_height_m: null })
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
