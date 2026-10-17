/** The bag a shopper checks out in the shop is the bag an agent fills in ChatGPT: same tool, same
 *  gate. These tests sit on the two things the UI is responsible for - showing what the service
 *  said, and not offering an order click the service would refuse. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { line, order, view } from "@/test/bag-fixtures"

type Handlers = Record<string, (body: Record<string, unknown>) => unknown>

async function mount(handlers: Handlers) {
  vi.resetModules()
  window.localStorage.clear()
  // The browser keeps one id; the bag behind it is the service's, so the fixture is a cart_id and
  // a stub for the tool that reads it.
  window.localStorage.setItem("byb.bag", JSON.stringify({ cart_id: "cart-1", room: { width_m: 4, depth_m: 3.5, height_m: 2.4 } }))
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const tool = url.split("/").pop() ?? ""
      const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null
      const answer = handlers[tool]?.(body ?? {})
      if (answer === undefined) return Promise.resolve(new Response(JSON.stringify({ detail: `no stub for ${tool}` }), { status: 500 }))
      return Promise.resolve(new Response(JSON.stringify({ tool, result: answer }), { status: 200 }))
    }),
  )
  const bag = await import("@/lib/bag")
  const { BagButton, BagDrawer } = await import("@/components/bag-drawer")
  render(
    <>
      <BagButton />
      <BagDrawer />
    </>,
  )
  bag.openBag()
  return { bag }
}

beforeEach(() => {
  vi.unstubAllGlobals()
})

describe("the bag drawer", () => {
  it("shows the bag the service described, not a local tally", async () => {
    const { bag } = await mount({ view_cart: () => view() })
    await waitFor(() => expect(bag.snapshot().bag?.cart_id).toBe("cart-1"))

    expect(await screen.findByText(line.name)).toBeInTheDocument()
    expect(screen.getAllByText("€899")).toHaveLength(2) // the line, and the bag total the service added up
    expect(screen.getByText("Fits")).toBeInTheDocument()
    expect(screen.getByRole("dialog", { name: "Your bag" })).toBeInTheDocument()
  })

  it("adds up the set the moment the service judges the pieces together", async () => {
    const set = { verdict: "tight", footprint_m2: 2.69, usable_area_m2: 13.3, coverage_pct: 20.2, tightest_walkway_m: 0.62, conflicts: ["The tightest walkway would be 0.62 m, under the 0.7 m a shopper has to reach the far side at."], footprint_estimated_from_listing: [], note: "" }
    await mount({ view_cart: () => view({ set }) })

    expect(await screen.findByText("Bought together")).toBeInTheDocument()
    expect(screen.getByText("Tight fit")).toBeInTheDocument()
    expect(screen.getByText(/2.69 m² on 13.3 m² usable/)).toBeInTheDocument()
    expect(screen.getByText(/tightest walkway would be 0.62 m/)).toBeInTheDocument()
  })

  it("keeps the order button out of reach until the bag is proven", async () => {
    await mount({ view_cart: () => view({ unproven: ["SOF-002"], checkout: { tool: "checkout", ready: false, needs: "words", how: "", refuses: "" } }) })

    expect(await screen.findByRole("button", { name: /Measure 1 unproven/ })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Place the order/ })).not.toBeInTheDocument()
    expect(screen.getByText(/SOF-002 has no cleared report/)).toBeInTheDocument()
  })

  it("asks the shopper for their own words, then writes the draft", async () => {
    const { bag } = await mount({ view_cart: () => view(), checkout: (body) => (body?.confirmation === "yes, order it" ? order : undefined) })

    const place = await screen.findByRole("button", { name: /Place the order/ })
    expect(place).toBeDisabled()

    fireEvent.change(screen.getByLabelText("Your own words"), { target: { value: "yes, order it" } })
    await waitFor(() => expect(place).toBeEnabled())
    fireEvent.click(place)

    expect(await screen.findByText(/Draft placed/)).toBeInTheDocument()
    expect(screen.getByText(/A person at the shop accepts or releases this draft/)).toBeInTheDocument()
    expect(bag.snapshot().order?.status).toBe("awaiting_merchant")
    expect(JSON.parse(window.localStorage.getItem("byb.bag") ?? "{}").cart_id).toBe(null)
  })

  it("counts what is in the bag from the service's answer", async () => {
    await mount({ view_cart: () => view({ items: 3, lines: [line, { ...line, sku: "ARM-001" }] }) })

    await waitFor(() => expect(screen.getByRole("button", { name: "Open your bag, 3 pieces" })).toBeInTheDocument())
  })

  it("names the room a verdict belongs to, and says when it is not the room on screen", async () => {
    await mount({
      view_cart: () => view({ room: { width_m: 3.6, depth_m: 3, height_m: 2.4 }, unproven: ["SOF-001"], lines: [{ ...line, verdict: "blocked", simulation_id: "sim-9", walkway_m: {} }] }),
    })

    expect(await screen.findByText("No clear spot")).toBeInTheDocument()
    expect(screen.getByText(/Measured for a/)).toBeInTheDocument()
    expect(screen.getByText("3.6 × 3 × 2.4 m")).toBeInTheDocument()
    expect(screen.getByText(/measure again before ordering/)).toBeInTheDocument()
  })
})
