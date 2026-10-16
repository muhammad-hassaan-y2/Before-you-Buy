import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AgentChat } from "@/components/agent-chat"

afterEach(() => vi.unstubAllGlobals())

function reply(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }))),
  )
}

describe("AgentChat", () => {
  it("opens with questions a shopper actually asks", () => {
    reply({ answer: "x", answered_by: "evolus" })
    render(<AgentChat />)
    expect(screen.getByRole("button", { name: /walkway do you check/i })).toBeInTheDocument()
  })

  it("keeps the thread and says which brain answered", async () => {
    reply({ answer: "The KURA fits: 0.6 m left at the front.", answered_by: "evolus", conversation_id: "c-7" })
    render(<AgentChat />)

    fireEvent.click(screen.getByRole("button", { name: /Will a 220 cm sofa fit/i }))
    await waitFor(() => expect(screen.getByText("The KURA fits: 0.6 m left at the front.")).toBeInTheDocument())

    expect(screen.getByText("Will a 220 cm sofa fit a 4 × 3.5 m room?")).toBeInTheDocument()
    expect(screen.getByText("Evolus agent")).toBeInTheDocument()
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect((init.headers as Record<string, string>)["X-Conversation-Id"]).toBeUndefined()
  })

  it("threads follow-ups onto the same conversation", async () => {
    reply({ answer: "yes", answered_by: "evolus", conversation_id: "c-7" })
    render(<AgentChat />)

    fireEvent.click(screen.getByRole("button", { name: /Will a 220 cm sofa fit/i }))
    await waitFor(() => expect(screen.getByText("yes")).toBeInTheDocument())

    fireEvent.change(screen.getByRole("textbox", { name: /Ask about a piece/i }), { target: { value: "and the door?" } })
    fireEvent.click(screen.getByRole("button", { name: "Send" }))
    await waitFor(() => expect((fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(2))
    const [, second] = (fetch as ReturnType<typeof vi.fn>).mock.calls[1]
    expect((second.headers as Record<string, string>)["X-Conversation-Id"]).toBe("c-7")
  })

  it("names the AMD model when Evolus did not reply", async () => {
    reply({ answer: "Two metres leaves 60 cm.", answered_by: "Qwen/Qwen2.5-3B-Instruct" })
    render(<AgentChat />)
    fireEvent.click(screen.getByRole("button", { name: /Will a 220 cm sofa fit/i }))

    await waitFor(() => expect(screen.getByText("Two metres leaves 60 cm.")).toBeInTheDocument())
    expect(screen.getByText("Qwen/Qwen2.5-3B-Instruct")).toBeInTheDocument()
  })

  it("tells the shopper when there is no brain behind the panel", async () => {
    reply({ detail: "neither Evolus nor an AMD model endpoint is configured" }, 503)
    render(<AgentChat />)
    fireEvent.click(screen.getByRole("button", { name: /Which SKU in the catalog/i }))

    await waitFor(() => expect(screen.getByText(/neither Evolus nor an AMD model endpoint is configured/)).toBeInTheDocument())
  })
})
