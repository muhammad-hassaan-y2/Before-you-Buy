import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ProductDetail } from "@/components/product-detail"
import { catalog, simulation } from "../../e2e/fixtures"

function serve({ status = 200, settled = simulation }: { status?: number; settled?: unknown } = {}) {
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes("/api/v1/catalog/")) {
      if (status !== 200) return Promise.resolve(new Response(JSON.stringify({ detail: `no SKU ${url.split("/").pop()}` }), { status }))
      return Promise.resolve(new Response(JSON.stringify(catalog[0]), { status: 200 }))
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
    expect(screen.getByText("€919")).toBeInTheDocument()
    expect(screen.getByText("€515")).toBeInTheDocument()
    expect(screen.getByText("€404 · 44.0%")).toBeInTheDocument()
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
    expect(screen.getByText("€919")).toBeInTheDocument()
  })

  it("admits the shelf has no such piece", async () => {
    serve({ status: 404 })
    render(<ProductDetail sku="BYB-NOTHING" />)

    await waitFor(() => expect(screen.getByText(/no SKU BYB-NOTHING/)).toBeInTheDocument())
    expect(screen.queryByRole("button", { name: /Simulate in my room/ })).not.toBeInTheDocument()
  })
})
