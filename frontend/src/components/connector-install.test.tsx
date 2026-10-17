import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ConnectorInstall } from "@/components/connector-install"
import type { ConnectGuide } from "@/lib/agent"

function guide(overrides: Partial<ConnectGuide> = {}): ConnectGuide {
  return {
    name: "buy-you-before",
    title: "Buy You Before fit assurance",
    url: "https://byb.test/mcp/",
    transport: "streamable-http",
    public: true,
    mode: "stateless",
    elicitation: false,
    auth: {
      type: "none",
      header: null,
      works_in: ["chatgpt", "claude.ai"],
      does_not_work_in: [],
      why: "Anyone with the URL can spend the shop's GPU jobs.",
    },
    capabilities: { tools: ["catalog_search", "fit_catalog"], resources: ["byb://catalog"], prompts: ["fit-my-room", "hold-the-fit"] },
    clients: {
      chatgpt: { label: "ChatGPT (web)", requires_https: true, steps: ["Apps -> Advanced -> Add custom MCP server.", "Paste the URL."], note: "ChatGPT takes no static key." },
      claude: { label: "Claude (claude.ai)", requires_https: true, steps: ["Customize -> Connectors -> + -> Add custom connector."], note: "claude.ai takes no typed key." },
      "claude-code": { label: "Claude Code", requires_https: false, command: "claude mcp add --transport http buy-you-before https://byb.test/mcp/" },
      cursor: { label: "Cursor", requires_https: false, config: { mcpServers: { "buy-you-before": { url: "https://byb.test/mcp/" } } } },
    },
    wiring: {},
    ...overrides,
  }
}

describe("ConnectorInstall", () => {
  it("walks a person through adding it to ChatGPT first", () => {
    render(<ConnectorInstall guide={guide()} fallbackUrl="http://localhost:3000/mcp/" />)

    expect(screen.getByText("Add the connector")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "ChatGPT (web)" })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByText("Apps -> Advanced -> Add custom MCP server.")).toBeInTheDocument()
    expect(screen.getByText("ChatGPT takes no static key.")).toBeInTheDocument()
  })

  it("gives Claude the connector path, and says a typed key is not part of it", () => {
    render(<ConnectorInstall guide={guide()} fallbackUrl="" />)

    fireEvent.click(screen.getByRole("button", { name: "Claude (claude.ai)" }))
    expect(screen.getByText("Customize -> Connectors -> + -> Add custom connector.")).toBeInTheDocument()
    expect(screen.getByText("claude.ai takes no typed key.")).toBeInTheDocument()
  })

  it("gives Claude Code the command and Cursor the config, ready to copy", () => {
    const copy = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: copy } })
    render(<ConnectorInstall guide={guide()} fallbackUrl="http://localhost:3000/mcp/" />)

    fireEvent.click(screen.getByRole("button", { name: "Claude Code" }))
    expect(screen.getByText("claude mcp add --transport http buy-you-before https://byb.test/mcp/")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Cursor" }))
    expect(screen.getByText(/mcpServers/)).toBeInTheDocument()
  })

  it("admits a local run has no address an outside assistant can add", () => {
    render(<ConnectorInstall guide={guide({ public: false, url: "/mcp/" })} fallbackUrl="https://tunnel.test/mcp/" />)

    expect(screen.getByText("https://tunnel.test/mcp/")).toBeInTheDocument()
    expect(screen.getByText(/no public address/i)).toBeInTheDocument()
  })

  it("says which doors a key locks out", () => {
    render(
      <ConnectorInstall
        guide={
          guide({
            auth: {
              type: "bearer",
              header: "Authorization: Bearer <MCP_CONNECT_TOKEN>",
              works_in: ["claude-code"],
              does_not_work_in: ["chatgpt", "claude.ai"],
              why: "ChatGPT sends no static key.",
            },
          })
        }
        fallbackUrl=""
      />,
    )

    expect(screen.getByText("Bearer key")).toBeInTheDocument()
    expect(screen.getByText(/needs this door open or an OAuth server/i)).toBeInTheDocument()
  })

  it("shows the mode the connector is actually running in", () => {
    render(<ConnectorInstall guide={guide({ mode: "sessions", elicitation: true })} fallbackUrl="" />)

    expect(screen.getByText("sessions")).toBeInTheDocument()
    expect(screen.getByText("streamable-http")).toBeInTheDocument()
    expect(screen.getByText("2 tools")).toBeInTheDocument()
  })
})
