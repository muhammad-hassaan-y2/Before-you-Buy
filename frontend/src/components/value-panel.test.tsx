import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ValuePanel } from "@/components/value-panel"

afterEach(() => vi.unstubAllGlobals())

const estimate = {
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

function respondingWith(handler: (url: string, init?: RequestInit) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      new Response(JSON.stringify(handler(String(input), init)), { status: 200, headers: { "Content-Type": "application/json" } }),
    ),
  )
}

describe("ValuePanel", () => {
  it("asks the service for the number instead of doing the maths in the browser", async () => {
    respondingWith(() => ({ tool: "returns_estimate", result: estimate }))
    render(<ValuePanel />)

    fireEvent.change(screen.getByLabelText("Orders / month"), { target: { value: "2000" } })
    fireEvent.change(screen.getByLabelText("Returns / month (%)"), { target: { value: "30" } })
    fireEvent.click(screen.getByRole("button", { name: "$$$" }))
    fireEvent.click(screen.getByRole("button", { name: /Recalculate/i }))

    await waitFor(() => expect(screen.getByText("€ 60300")).toBeInTheDocument())
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe("/agent/tools/returns_estimate")
    expect(JSON.parse(String(calls[0][1].body))).toMatchObject({ orders_per_month: 2000, price_band: "$$$", return_rate: 0.3 })
    expect(screen.getByText("40.2")).toBeInTheDocument()
    expect(screen.getByText(/67 % fit-driven/)).toBeInTheDocument()
  })

  it("shows what the service said when it refuses the assumptions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "return_rate must be between 0 and 1" }), { status: 422 })),
    )
    render(<ValuePanel />)
    fireEvent.click(screen.getByRole("button", { name: /Recalculate/i }))

    expect(await screen.findByText("return_rate must be between 0 and 1")).toBeInTheDocument()
  })

  it("claims nothing until it has a number back", () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })))
    render(<ValuePanel />)
    expect(screen.queryByText(/Revenue kept/)).not.toBeInTheDocument()
  })
})
