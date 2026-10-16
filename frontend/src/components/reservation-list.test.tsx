import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ReservationList } from "@/components/reservation-list"

afterEach(() => vi.unstubAllGlobals())

const holds = [
  {
    id: "run-1",
    simulation_id: "sim-42",
    sku: "SOFA-302",
    name: "Ektorp 3-seat sofa",
    verdict: "fits",
    confirmation: "yes, hold it for me",
    status: "pending_merchant",
    created_at: "2026-10-16T09:12:00Z",
  },
]

describe("ReservationList", () => {
  it("shows the shopper's own words and the evidence behind the hold", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(holds), { status: 200 })))
    render(<ReservationList />)

    const row = await screen.findByText("Ektorp 3-seat sofa")
    expect(screen.getByText("“yes, hold it for me”")).toBeInTheDocument()
    expect(screen.getByText("pending merchant")).toBeInTheDocument()
    expect(row.parentElement).toHaveTextContent("SOFA-302")
    expect(screen.getByRole("link", { name: /fit evidence/ })).toHaveAttribute("href", "/api/v1/simulations/sim-42")
  })

  it("explains why there is nothing on the list rather than leaving it blank", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify([]), { status: 200 })))
    render(<ReservationList />)

    expect(await screen.findByText(/A hold needs the shopper/)).toBeInTheDocument()
  })

  it("is honest about a service it cannot reach", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("unavailable", { status: 503 })))
    render(<ReservationList />)

    expect(await screen.findByText(/A hold needs the shopper/)).toBeInTheDocument()
  })
})
