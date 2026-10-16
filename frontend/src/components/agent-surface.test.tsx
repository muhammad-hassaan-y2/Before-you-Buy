import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AgentSurface } from "@/components/agent-surface"

afterEach(() => vi.unstubAllGlobals())

function toolsReply() {
  return {
    tools: [
      { name: "catalog_search", description: "Find furniture in the shop's catalog." },
      { name: "start_journey", description: "Run the whole fit-assurance process." },
    ],
  }
}

describe("AgentSurface", () => {
  it("lists the capabilities the agent service publishes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(toolsReply()), { status: 200 })))
    render(<AgentSurface />)

    await waitFor(() => expect(screen.getByText("catalog_search")).toBeInTheDocument())
    expect(screen.getByText("start_journey")).toBeInTheDocument()
    expect(screen.getByText("Find furniture in the shop's catalog.")).toBeInTheDocument()
  })

  it("offers the MCP door an Evolus connector can be pointed at", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(toolsReply()), { status: 200 })))
    render(<AgentSurface />)

    expect(await screen.findByText(/\/mcp\/$/)).toBeInTheDocument()
  })

  it("says so when agent-service is not there", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")))
    render(<AgentSurface />)

    expect(await screen.findByText(/not reachable/)).toBeInTheDocument()
  })
})
