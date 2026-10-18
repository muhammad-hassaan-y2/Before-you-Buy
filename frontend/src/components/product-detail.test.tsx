import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ProductDetail } from "@/components/product-detail"
import { catalog, simulation } from "../../e2e/fixtures"

function serve({
  status = 200,
  settled = simulation,
  stock = [] as unknown[],
  rows = catalog,
}: { status?: number; settled?: unknown; stock?: unknown[]; rows?: unknown[] } = {}) {
  const json = (body: unknown, code = 200) => new Response(JSON.stringify(body), { status: code })
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith("/api/v1/stock")) return Promise.resolve(json(stock))
    if (url.endsWith("/api/v1/stock/events")) return Promise.resolve(json([]))
    if (url.endsWith("/api/v1/catalog")) return Promise.resolve(json(rows))
    if (url.includes("/api/v1/catalog/")) {
      if (status !== 200) return Promise.resolve(new Response(JSON.stringify({ detail: `no SKU ${url.split("/").pop()}` }), { status }))
      return Promise.resolve(new Response(JSON.stringify(rows[0]), { status: 200 }))
    }
    if (url.endsWith("/api/v1/simulations") && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify({ id: simulation.id, status: "pending" }), { status: 202 }))
    }
    if (url.includes("/api/v1/simulations/")) return Promise.resolve(new Response(JSON.stringify(settled), { status: 200 }))
    return Promise.resolve(new Response(JSON.stringify({ detail: "unexpected " + url }), { status: 500 }))
  })
  vi.stubGlobal("fetch", fetch)
  return fetch
}

describe("ProductDetail", () => {
  it("quotes the terms the catalog derived, and says where they come from", async () => {
    serve()
    render(<ProductDetail sku="BYB-KURA-3S" />)

    await waitFor(() => expect(screen.getByRole("heading", { name: "KURA three-seat sofa" })).toBeInTheDocument())
    // The price is on the listing and again on the bar that follows it down the page.
    expect(screen.getAllByText("€919")).toHaveLength(2)
    expect(screen.getByText("€515")).toBeInTheDocument()
    expect(screen.getByText(/margin 44\.0 %/)).toBeInTheDocument()
    expect(screen.getByText("18 days")).toBeInTheDocument()
    expect(screen.getByText("Porto Frame Works · PT")).toBeInTheDocument()
    expect(screen.getByText(/no supplier feed connected/)).toBeInTheDocument()
    expect(screen.getByText("https://shop.example.com/p/kura-kura-three-seat-sofa-bybkura3s/")).toBeInTheDocument()
  })

  it("runs the listing itself through the pipeline and shows what the geometry decided", async () => {
    const fetch = serve()
    render(<ProductDetail sku="BYB-KURA-3S" />)
    await waitFor(() => expect(screen.getByRole("button", { name: /Simulate in my room/ })).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /Simulate in my room/ }))

    const posted = await waitFor(() => {
      const call = fetch.mock.calls.find(([url, init]) => String(url).endsWith("/api/v1/simulations") && init?.method === "POST")
      if (!call) throw new Error("no simulation was submitted")
      return call
    })
    const form = posted[1]?.body as FormData
    expect(form.get("link")).toBe(catalog[0].commerce.product_url)
    expect(form.get("shopper_notes")).toBe("KURA KURA three-seat sofa linen")
    expect(form.get("room_width_m")).toBe("4")

    await waitFor(() => expect(screen.getByText("Fits with room to move")).toBeInTheDocument())
    expect(screen.getByRole("img", { name: /Room 4 by 3.5 metres/ })).toBeInTheDocument()
    expect(screen.getByText("200 × 90 × 84 cm")).toBeInTheDocument()
  })

  it("keeps the shop standing when the sweep says the piece does not fit", async () => {
    serve({ settled: { ...simulation, fit_report: { ...simulation.fit_report, verdict: "too_large" } } })
    render(<ProductDetail sku="BYB-KURA-3S" />)
    await waitFor(() => expect(screen.getByRole("button", { name: /Simulate in my room/ })).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /Simulate in my room/ }))
    await waitFor(() => expect(screen.getByText("Too large for this room")).toBeInTheDocument())
    expect(screen.getAllByText("€919")).toHaveLength(2)
  })

  it("stands on the shelf's own count and offers the rest of that shelf", async () => {
    serve({
      stock: [
        {
          sku: "BYB-KURA-3S",
          name: "KURA three-seat sofa",
          on_hand: 6,
          reserved: 2,
          available: 2,
          state: "low",
          volume_m3: 1.512,
          lead_days: 18,
          next_lot_in_days: 18,
          basis: "derived from the SKU",
        },
      ],
      rows: [catalog[0], { ...catalog[1], sku: "BYB-VIDGA-2S", name: "VIDGA two-seat sofa", category: "sofa" }],
    })
    render(<ProductDetail sku="BYB-KURA-3S" />)

    await waitFor(() => expect(screen.getAllByText("2 left · 2 held")).toHaveLength(2))
    expect(screen.getByText(/shelf live · 1 counts/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole("heading", { name: /More on the sofa shelf/ })).toBeInTheDocument())
    expect(screen.getByRole("link", { name: /VIDGA two-seat sofa/ })).toHaveAttribute("href", "/product/BYB-VIDGA-2S")
    expect(screen.queryByRole("link", { name: /BILLY bookcase 80 cm/ })).not.toBeInTheDocument()
  })

  it("admits the shelf has no such piece", async () => {
    serve({ status: 404 })
    render(<ProductDetail sku="BYB-NOTHING" />)

    await waitFor(() => expect(screen.getByText(/no SKU BYB-NOTHING/)).toBeInTheDocument())
    expect(screen.queryByRole("button", { name: /Simulate in my room/ })).not.toBeInTheDocument()
  })
})
