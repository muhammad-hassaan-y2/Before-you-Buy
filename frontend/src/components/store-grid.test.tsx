import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { StoreGrid } from "@/components/store-grid"
import type { StockRow } from "@/lib/api"

/** The shop's live layer is what this test exists to pin: which room got streamed, how each verdict
 *  lands on its own card, and what the shelf counts say. fetch is stubbed for the catalog only. */
const live = vi.hoisted(() => ({
  shelf: {
    bySku: {} as Record<string, StockRow>,
    events: [] as { at: string; action: string; sku: string; qty: number }[],
    live: false,
    error: null as string | null,
    refresh: vi.fn(),
  },
  sweep: vi.fn(),
}))

vi.mock("@/lib/live", () => ({
  useShelf: () => live.shelf,
  streamSweep: live.sweep,
}))

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

const stock = (over: Partial<StockRow>): StockRow => ({
  sku: over.sku ?? sofa.sku,
  name: over.name ?? sofa.name,
  on_hand: 6,
  reserved: 0,
  available: 6,
  state: "in_stock",
  volume_m3: 1.512,
  lead_days: 18,
  next_lot_in_days: 18,
  basis: "derived from the SKU",
  ...over,
})

/** Replay the sweep the way agent-service streams it: a start, one frame per settled simulation, a done. */
function replay(events: Record<string, unknown>[]) {
  live.sweep.mockImplementation(async (_room: unknown, onEvent: (event: any) => void) => {
    for (const event of events) onEvent(event)
  })
}

const verdicts = [
  { event: "start", total: 2 },
  { event: "verdict", of: 1, total: 2, sku: sofa.sku, verdict: "fits", simulation_id: "sim-1", ms: 2400 },
  { event: "verdict", of: 2, total: 2, sku: bookcase.sku, verdict: "too_large", simulation_id: "sim-2", ms: 1900 },
  { event: "done", checked: 2, fits: 1, does_not_fit: 1, unproven: 0, note: "Only the geometry engine's own verdict is reported here." },
]

/** The shop reads the catalog through the gateway; everything live comes from the mocked layer. */
function serve() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input).endsWith("/api/v1/catalog")
        ? Promise.resolve(new Response(JSON.stringify([sofa, bookcase]), { status: 200 }))
        : Promise.resolve(new Response(JSON.stringify({ detail: "unexpected " + String(input) }), { status: 500 })),
    ),
  )
}

describe("StoreGrid", () => {
  beforeEach(() => {
    live.shelf.bySku = {}
    live.shelf.events = []
    live.shelf.live = false
    live.shelf.error = null
  })

  afterEach(() => {
    live.sweep.mockReset()
  })

  it("shows the shelf with the terms the catalog derived", async () => {
    serve()
    replay([])
    render(<StoreGrid />)

    await waitFor(() => expect(screen.getByText("KURA three-seat sofa")).toBeInTheDocument())
    expect(screen.getByText("€919")).toBeInTheDocument()
    expect(screen.getByText("€399")).toBeInTheDocument()
    expect(screen.getByText("18 days · pallet freight")).toBeInTheDocument()
    expect(screen.getAllByText("reading the shelf…")).toHaveLength(2)
    expect(screen.getByRole("link", { name: /KURA three-seat sofa/ })).toHaveAttribute("href", "/product/BYB-KURA-3S")
  })

  it("measures the first cards the moment the shelf opens", async () => {
    serve()
    replay([])
    render(<StoreGrid />)

    await waitFor(() => expect(live.sweep).toHaveBeenCalledTimes(1))
    expect(live.sweep.mock.calls[0][0]).toMatchObject({ room_width_m: 4, room_depth_m: 3.5, room_height_m: 2.4, limit: 8 })
  })

  it("badges each card with the verdict its own simulation settled to", async () => {
    serve()
    replay(verdicts)
    render(<StoreGrid />)

    await waitFor(() => expect(screen.getByText("Fits")).toBeInTheDocument())
    expect(screen.getByText("Too large")).toBeInTheDocument()
    expect(screen.getByText(/1 of this sweep cleared the 4 × 3.5 m room/)).toBeInTheDocument()
  })

  it("streams the room on the bar, not the one it was opened with", async () => {
    serve()
    replay(verdicts)
    render(<StoreGrid />)
    await waitFor(() => expect(screen.getByText("KURA three-seat sofa")).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText("Width in metres"), { target: { value: "3.6" } })
    fireEvent.click(screen.getByRole("button", { name: /Measure 8 in my room/ }))

    await waitFor(() => expect(live.sweep.mock.calls[1][0]).toMatchObject({ room_width_m: 3.6, room_depth_m: 3.5, limit: 8 }))
    await waitFor(() => expect(screen.getByText(/cleared the 3.6 × 3.5 m room/)).toBeInTheDocument())
  })

  it("puts the shelf's own counts on the card and on the bar", async () => {
    serve()
    replay([])
    live.shelf.bySku = {
      [sofa.sku]: stock({ available: 3, reserved: 2, state: "low" }),
      [bookcase.sku]: stock({ sku: bookcase.sku, name: bookcase.name, state: "made_to_order", available: 0, on_hand: 0, lead_days: 45 }),
    }
    live.shelf.live = true
    live.shelf.events = [{ at: new Date().toISOString(), action: "claimed", sku: sofa.sku, qty: 2 }]

    render(<StoreGrid />)
    await waitFor(() => expect(screen.getByText("3 left · 2 held")).toBeInTheDocument())
    expect(screen.getByText("Cut after your order · 45 days")).toBeInTheDocument()
    expect(screen.getByText("shelf live · 2 counts")).toBeInTheDocument()
    expect(screen.getByText(/Held/)).toBeInTheDocument()
  })

  it("narrows the shelf with a search and a category", async () => {
    serve()
    replay([])
    render(<StoreGrid />)
    // The result count is the only `span.num` in the bar; the rail's per-shelf totals are `<p>`.
    const shown = () => screen.getByText(/piece/, { selector: "span.num" })
    await waitFor(() => expect(shown()).toHaveTextContent("2 pieces"))

    fireEvent.change(screen.getByLabelText("Search the catalog"), { target: { value: "linen" } })
    await waitFor(() => expect(shown()).toHaveTextContent("1 piece"))
    expect(screen.queryByText("BILLY bookcase 80 cm")).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Search the catalog"), { target: { value: "" } })
    fireEvent.click(screen.getByRole("button", { name: "bookcase" }))
    await waitFor(() => expect(screen.queryByText("KURA three-seat sofa")).not.toBeInTheDocument())
    expect(shown()).toHaveTextContent("1 piece")
  })

  it("measures the shelf a tile chose, not the whole catalog", async () => {
    serve()
    replay([])
    render(<StoreGrid />)
    await waitFor(() => expect(screen.getByText("KURA three-seat sofa")).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: "sofa" }))
    await waitFor(() => expect(live.sweep.mock.calls[1][0]).toMatchObject({ category: "sofa" }))
    expect(screen.queryByText("BILLY bookcase 80 cm")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "sofa" }))
    await waitFor(() => expect(live.sweep.mock.calls[2][0]).toMatchObject({ category: null }))
    expect(screen.getByText("BILLY bookcase 80 cm")).toBeInTheDocument()
  })

  it("says so when the sweep refuses the room", async () => {
    serve()
    replay([{ event: "error", detail: "nothing in the catalog matches that" }])
    render(<StoreGrid />)
    await waitFor(() => expect(screen.getByText("KURA three-seat sofa")).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /Measure 8 in my room/ }))
    await waitFor(() => expect(screen.getByText(/nothing in the catalog matches that/)).toBeInTheDocument())
    expect(screen.getAllByText("Not measured")).toHaveLength(2)
  })

  it("stops mid-sweep and keeps the verdicts it already settled", async () => {
    serve()
    let release = () => {}
    live.sweep.mockImplementation(
      (_room: unknown, onEvent: (event: any) => void) =>
        new Promise<void>((resolve) => {
          onEvent(verdicts[1])
          release = resolve
        }),
    )
    render(<StoreGrid />)

    await waitFor(() => expect(screen.getByText("Fits")).toBeInTheDocument())
    fireEvent.click(screen.getByRole("button", { name: "1 of 2 measured" }))
    expect(screen.getByRole("button", { name: /Measure 8 in my room/ })).toBeEnabled()
    expect(screen.getByText("Fits")).toBeInTheDocument()
    release()
  })
})
