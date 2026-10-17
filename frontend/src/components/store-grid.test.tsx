import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { StoreGrid } from "@/components/store-grid"

const sofa = {
  sku: "BYB-KURA-3S",
  name: "KURA three-seat sofa",
  brand: "KURA",
  category: "sofa",
  material: "linen",
  price_band: "$$",
  geometry: { width_cm: 200, depth_cm: 90, height_cm: 84, clearance_cm: 10 },
  commerce: {
    currency: "EUR",
    retail_eur: 919,
    cost_eur: 515,
    margin_eur: 404,
    margin_pct: 44,
    volume_m3: 1.512,
    supplier: { name: "Porto Frame Works", region: "PT" },
    lead_days: 18,
    freight: "pallet",
    product_url: "https://shop.example.com/p/kura/",
    basis: "derived from the SKU's price band, category and box size",
  },
}

const bookcase = {
  ...sofa,
  sku: "BYB-BILLY-80",
  name: "BILLY bookcase 80 cm",
  brand: "BILLY",
  category: "bookcase",
  material: "oak veneer",
  price_band: "$",
  commerce: { ...sofa.commerce, retail_eur: 399, margin_pct: 55.9, lead_days: 15, freight: "parcel" },
}

const sweep = {
  tool: "fit_catalog",
  result: {
    room: { width_m: 3.6, depth_m: 3, height_m: 2.4, measured_from_photo: false },
    checked: 2,
    fits: [{ sku: "BYB-KURA-3S", name: sofa.name, price_band: "$$", score: 0.8, simulation_id: "sim-1", status: "completed", verdict: "fits", coverage_pct: 12, walkway_m: { front: 0.6 }, reason: null, ms: 2400, size_cm: { width_cm: 200, depth_cm: 90, height_cm: 84 }, tightest_walkway_m: 0.6, verify: null }],
    does_not_fit: [{ sku: "BYB-BILLY-80", name: bookcase.name, price_band: "$", score: 0.6, simulation_id: "sim-2", status: "completed", verdict: "too_large", coverage_pct: 0, walkway_m: {}, reason: null, ms: 1900, size_cm: { width_cm: 80, depth_cm: 28, height_cm: 202 }, tightest_walkway_m: null, verify: null }],
    unproven: [],
    note: "Only the geometry engine's own verdict is reported here.",
  },
}

/** The shop reads two services: the gateway for the shelf, agent-service for the measured sweep. */
function serve(sweepBody: unknown = sweep, sweepStatus = 200) {
  const fetch = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>((input) => {
    const url = String(input)
    if (url.endsWith("/api/v1/catalog")) return Promise.resolve(new Response(JSON.stringify([sofa, bookcase]), { status: 200 }))
    if (url.endsWith("/agent/tools/fit_catalog")) return Promise.resolve(new Response(JSON.stringify(sweepBody), { status: sweepStatus }))
    return Promise.resolve(new Response(JSON.stringify({ detail: "unexpected " + url }), { status: 500 }))
  })
  vi.stubGlobal("fetch", fetch)
  return fetch
}

describe("StoreGrid", () => {
  it("shows the shelf with the terms the catalog derived", async () => {
    serve()
    render(<StoreGrid />)

    await waitFor(() => expect(screen.getByText("KURA three-seat sofa")).toBeInTheDocument())
    expect(screen.getByText("€919")).toBeInTheDocument()
    expect(screen.getByText("€399")).toBeInTheDocument()
    expect(screen.getByText("18 days, pallet freight")).toBeInTheDocument()
    expect(screen.getAllByText("Not measured")).toHaveLength(2)
    expect(screen.getByRole("link", { name: /KURA three-seat sofa/ })).toHaveAttribute("href", "/product/BYB-KURA-3S")
  })

  it("badges every card with the verdict the geometry engine gave", async () => {
    const fetch = serve()
    render(<StoreGrid />)
    await waitFor(() => expect(screen.getByText("KURA three-seat sofa")).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText("Width (m)"), { target: { value: "3.6" } })
    fireEvent.click(screen.getByRole("button", { name: /Measure in my room/ }))

    await waitFor(() => expect(screen.getByText("Fits")).toBeInTheDocument())
    expect(screen.getByText("Too large")).toBeInTheDocument()
    const call = fetch.mock.calls.find(([url, init]) => String(url).endsWith("/agent/tools/fit_catalog") && init?.method === "POST")
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ room_width_m: 3.6, room_depth_m: 3.5, limit: 8 })
    expect(screen.getByText(/2 pieces measured in a 3.6 × 3 m room/)).toBeInTheDocument()
  })

  it("narrows the shelf with a search and a category", async () => {
    serve()
    render(<StoreGrid />)
    await waitFor(() => expect(screen.getByText("2 pieces")).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText("Search the catalog"), { target: { value: "linen" } })
    await waitFor(() => expect(screen.getByText("1 piece")).toBeInTheDocument())
    expect(screen.queryByText("BILLY bookcase 80 cm")).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Search the catalog"), { target: { value: "" } })
    fireEvent.click(screen.getByRole("button", { name: "bookcase" }))
    await waitFor(() => expect(screen.queryByText("KURA three-seat sofa")).not.toBeInTheDocument())
  })

  it("says so when the sweep refuses the room", async () => {
    serve({ detail: "nothing in the catalog matches that" }, 500)
    render(<StoreGrid />)
    await waitFor(() => expect(screen.getByText("KURA three-seat sofa")).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /Measure in my room/ }))
    await waitFor(() => expect(screen.getByText(/nothing in the catalog matches that/)).toBeInTheDocument())
    expect(screen.getAllByText("Not measured")).toHaveLength(2)
  })
})
