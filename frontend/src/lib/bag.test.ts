/** The bag store against the tool contract. What is locked down is the division of labour: the
 *  browser keeps one id and the room it is shopping for, agent-service keeps the lines, the
 *  prices and the gate. A bag the service no longer has is an empty shelf, not an error page. */

import { beforeEach, describe, expect, it, vi } from "vitest"

import { order, view } from "@/test/bag-fixtures"

/** A tool's answer, or the sentence it refuses with. `refuse()` mirrors the gateway's 422 body. */
type Handler = (body: Record<string, unknown>) => unknown
type Handlers = Record<string, Handler>

function refuse(detail: string, status = 422): Handler {
  return () => ({ __refusal: { detail, status } })
}

interface Harness {
  bag: typeof import("./bag")
  calls: [string, Record<string, unknown> | null][]
}

/** A fresh copy of the module per test: the store is a singleton, so its state is re-imported. */
async function fresh(handlers: Handlers = {}): Promise<Harness> {
  vi.resetModules()
  window.localStorage.clear()
  const calls: [string, Record<string, unknown> | null][] = []
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const tool = url.split("/").pop() ?? ""
      const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null
      calls.push([url, body])
      const answer = handlers[tool]?.(body ?? {})
      if (answer === undefined) return Promise.resolve(new Response(JSON.stringify({ detail: `no stub for ${tool}` }), { status: 500 }))
      const refusal = (answer as { __refusal?: { detail: string; status: number } }).__refusal
      if (refusal) return Promise.resolve(new Response(JSON.stringify({ detail: refusal.detail }), { status: refusal.status }))
      return Promise.resolve(new Response(JSON.stringify({ tool, result: answer }), { status: 200 }))
    }),
  )
  const bag = await import("./bag")
  return { bag, calls }
}

beforeEach(() => {
  vi.unstubAllGlobals()
})

describe("the bag store", () => {
  it("keeps the id the service mints, and nothing else", async () => {
    const { bag, calls } = await fresh({ add_to_cart: () => view() })

    const result = await bag.addToBag("SOF-001")

    expect(result.ok).toBe(true)
    expect(calls[0][1]).toMatchObject({ sku: "SOF-001", cart_id: null, quantity: 1 })
    expect(bag.snapshot().bag?.cart_id).toBe("cart-1")
    expect(JSON.parse(window.localStorage.getItem("byb.bag") ?? "{}")).toMatchObject({ cart_id: "cart-1" })
  })

  it("opens the bag the moment a piece goes in", async () => {
    const { bag } = await fresh({ add_to_cart: () => view() })
    await bag.addToBag("SOF-001")
    expect(bag.snapshot().open).toBe(true)
  })

  it("sends the room on screen with every write", async () => {
    const { bag, calls } = await fresh({ add_to_cart: () => view(), measure_cart: () => view() })
    bag.trackRoom({ width_m: 3.6, depth_m: 3, height_m: 2.4 })

    await bag.addToBag("SOF-001", { simulationId: "sim-1" })
    await bag.measureBag()

    expect(calls[0][1]).toMatchObject({ room_width_m: 3.6, room_depth_m: 3, room_height_m: 2.4, simulation_id: "sim-1" })
    expect(calls[1][1]).toMatchObject({ cart_id: "cart-1", room_width_m: 3.6 })
  })

  it("hands the shopper the service's own refusal, and keeps the bag", async () => {
    const { bag } = await fresh({
      add_to_cart: () => view({ unproven: ["SOF-002"], checkout: { ...view().checkout, ready: false } }),
      checkout: refuse("nothing is sold unchecked: SOF-002 has no cleared fit report. Run measure_cart on this bag, then put only what the engine clears in the order."),
    })
    await bag.addToBag("SOF-001")

    const result = await bag.placeOrder("they seemed keen")

    expect(result.ok).toBe(false)
    expect(result.error).toMatch(/nothing is sold unchecked/)
    expect(bag.snapshot().error).toMatch(/unchecked/)
    expect(bag.snapshot().bag?.cart_id).toBe("cart-1")
  })

  it("treats a bag the service lost as an empty shelf", async () => {
    const { bag } = await fresh({ view_cart: refuse("unknown cart 'cart-9'. Bags live in this process; start one with add_to_cart.") })
    window.localStorage.setItem("byb.bag", JSON.stringify({ cart_id: "cart-9", room: { width_m: 4, depth_m: 3.5, height_m: 2.4 } }))

    const result = await bag.refreshBag()

    expect(result.error).toBe(null)
    expect(bag.snapshot().bag).toBe(null)
    expect(bag.snapshot().error).toBe(null)
    expect(JSON.parse(window.localStorage.getItem("byb.bag") ?? "{}").cart_id).toBe(null)
  })

  it("writes the draft and starts the next bag empty", async () => {
    const { bag, calls } = await fresh({ add_to_cart: () => view(), checkout: () => order })
    await bag.addToBag("SOF-001")

    const result = await bag.placeOrder("yes, order it")

    expect(result.order?.status).toBe("awaiting_merchant")
    expect(bag.snapshot().bag).toBe(null)
    expect(JSON.parse(window.localStorage.getItem("byb.bag") ?? "{}").cart_id).toBe(null)
    expect(calls[1]?.[1]).toMatchObject({ cart_id: "cart-1", confirmation: "yes, order it" })
  })

  it("does not ask the service for a bag it does not have", async () => {
    const { bag, calls } = await fresh()
    const result = await bag.refreshBag()
    expect(result.ok).toBe(true)
    expect(calls).toHaveLength(0)
  })

  it("refuses to check out a bag it has never had", async () => {
    const { bag, calls } = await fresh()
    const result = await bag.placeOrder("yes, order it")
    expect(result.ok).toBe(false)
    expect(result.error).toMatch(/empty/)
    expect(calls).toHaveLength(0)
  })

  it("only offers the order button for words the service accepts", async () => {
    const { bag } = await fresh()
    expect(bag.soundsConfirmed("yes, order it")).toBe(true)
    expect(bag.soundsConfirmed("go ahead")).toBe(true)
    expect(bag.soundsConfirmed("the shopper seemed keen")).toBe(false)
    expect(bag.soundsConfirmed("no")).toBe(false)
    expect(bag.soundsConfirmed("")).toBe(false)
  })
})
