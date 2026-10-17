import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AgentSurface } from "@/components/agent-surface"
import type { ConnectGuide } from "@/lib/agent"

afterEach(() => vi.unstubAllGlobals())

const TOOLS = {
  tools: [
    { name: "catalog_search", description: "Find furniture in the shop's catalog." },
    { name: "start_journey", description: "Run the whole fit-assurance process." },
  ],
}

const GUIDE: ConnectGuide = {
  name: "buy-you-before",
  title: "Buy You Before fit assurance",
  url: "https://byb.test/mcp/",
  transport: "streamable-http",
  public: true,
  mode: "stateless",
  elicitation: false,
  auth: { type: "none", header: null, works_in: ["chatgpt"], does_not_work_in: [], why: "Anyone with the URL can call it." },
  capabilities: { tools: ["catalog_search"], resources: ["byb://catalog"], prompts: ["fit-my-room"] },
  clients: {
    chatgpt: { label: "ChatGPT (web)", requires_https: true, steps: ["Apps -> Advanced -> Add custom MCP server."] },
    claude: { label: "Claude (claude.ai)", requires_https: true, steps: ["Settings -> Connectors."] },
  },
  wiring: {},
}

/** Two doors on one origin: the page reads the tool list and the install guide separately. */
function serve({ withGuide = true }: { withGuide?: boolean } = {}) {
  return vi.fn((input: RequestInfo | URL) => {
    const connect = String(input).endsWith("/connect")
    // A service that has no /agent/connect yet answers 404, which is what a real one does.
    if (connect && !withGuide) return Promise.resolve(new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }))
    return Promise.resolve(new Response(JSON.stringify(connect ? GUIDE : TOOLS), { status: 200, headers: { "Content-Type": "application/json" } }))
  })
}

describe("AgentSurface", () => {
  it("lists the capabilities the agent service publishes", async () => {
    vi.stubGlobal("fetch", serve())
    render(<AgentSurface />)

    await waitFor(() => expect(screen.getByText("catalog_search")).toBeInTheDocument())
    expect(screen.getByText("start_journey")).toBeInTheDocument()
    expect(screen.getByText("Find furniture in the shop's catalog.")).toBeInTheDocument()
  })

  it("offers the MCP door an Evolus connector can be pointed at", async () => {
    vi.stubGlobal("fetch", serve({ withGuide: false }))
    render(<AgentSurface />)

    expect(await screen.findByText(/\/mcp\/$/)).toBeInTheDocument()
  })

  it("hands a person the guide that adds this connector to ChatGPT or Claude", async () => {
    vi.stubGlobal("fetch", serve())
    render(<AgentSurface />)

    expect(await screen.findByText("Add the connector")).toBeInTheDocument()
    expect(screen.getByText("https://byb.test/mcp/")).toBeInTheDocument()
    expect(screen.getByText("Apps -> Advanced -> Add custom MCP server.")).toBeInTheDocument()
  })

  it("says so when agent-service is not there", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")))
    render(<AgentSurface />)

    expect(await screen.findByText(/not reachable/)).toBeInTheDocument()
  })
})
