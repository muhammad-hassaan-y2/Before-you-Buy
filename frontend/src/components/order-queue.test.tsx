import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { OrderQueue } from "@/components/order-queue"

afterEach(() => vi.unstubAllGlobals())

const drafts = [
  {
    id: "ord-42beef",
    cart_id: "cart-7",
    status: "awaiting_merchant",
    total_eur: 1318,
    margin_eur: 627,
    confirmation: "yes, order both of them",
    created_at: "2026-10-17T09:04:00Z",
  },
]

describe("OrderQueue", () => {
  it("shows the words the shopper typed and what the draft is worth", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(drafts), { status: 200 })))
    render(<OrderQueue />)

    expect(await screen.findByText("“yes, order both of them”")).toBeInTheDocument()
    expect(screen.getByText("€1,318")).toBeInTheDocument()
    expect(screen.getByText("+€627")).toBeInTheDocument()
    expect(screen.getByText("awaiting merchant")).toBeInTheDocument()
    expect(screen.getByText("ord-42be")).toBeInTheDocument()
  })

  it("says why the queue is empty instead of showing a blank card", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify([]), { status: 200 })))
    render(<OrderQueue />)

    expect(await screen.findByText(/A draft needs the shopper/)).toBeInTheDocument()
  })

  it("treats an unreachable service as an empty queue, not a crash", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("unavailable", { status: 503 })))
    render(<OrderQueue />)

    expect(await screen.findByText(/A draft needs the shopper/)).toBeInTheDocument()
  })
})
