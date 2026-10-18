"use client"

import { Globe, Monitor, Plug, Ruler, Search, ShoppingBag, Wrench, type LucideIcon } from "lucide-react"
import { useEffect, useState } from "react"

import { ConnectorInstall } from "@/components/connector-install"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { fetchConnect, fetchTools, type ConnectGuide, type ToolSpec } from "@/lib/agent"

/** Where this page can reach the connector. Read from the window, so it is only called once the
 *  component is a browser: Evolus and ChatGPT need https, localhost does not. */
function browserMcpUrl(): string {
  const origin = window.location.origin
  const host = window.location.hostname
  const secure = origin.startsWith("https:") || (origin.startsWith("http:") && !["localhost", "127.0.0.1", "::1"].includes(host))
  return `${secure ? origin.replace(/^http:/, "https:") : origin}/mcp/`
}

const TOOL_ICON: Record<string, LucideIcon> = {
  fit_catalog: Ruler,
  fit_check: Ruler,
  search_catalog: Search,
  returns_estimate: Globe,
  bag: ShoppingBag,
}

/** Three ways in, one set of capabilities behind them. */
function Doors() {
  const doors = [
    { icon: Plug, label: "MCP connector", who: "the agent" },
    { icon: Globe, label: "REST", who: "an Evolus step" },
    { icon: Monitor, label: "This page", who: "a shopper" },
  ]
  return (
    <div className="flex items-stretch gap-2" aria-label="Three doors into the same capabilities">
      {doors.map(({ icon: Icon, label, who }, at) => (
        <div key={label} className="flex flex-1 items-center">
          <div className="flex-1 rounded-lg border border-border p-3 text-center">
            <Icon className="mx-auto size-5 text-primary" />
            <p className="mt-1.5 text-xs font-medium">{label}</p>
            <p className="text-[11px] text-muted-foreground">{who}</p>
          </div>
          {at < doors.length - 1 && <span aria-hidden className="mx-1 text-muted-foreground">+</span>}
        </div>
      ))}
    </div>
  )
}

/** The capability surface an Evolus agent, a workflow step or an MCP client is handed. */
export function AgentSurface() {
  const [tools, setTools] = useState<ToolSpec[]>([])
  const [guide, setGuide] = useState<ConnectGuide | null>(null)
  const [mcpUrl, setMcpUrl] = useState("")

  useEffect(() => {
    fetchTools().then(setTools, () => setTools([]))
    fetchConnect().then((known) => {
      setMcpUrl(browserMcpUrl())
      setGuide(known)
    })
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>What the agent is allowed to do
        </CardTitle>
        <CardDescription>
One set of capabilities, three doors. The agent can only do what a shopper&apos;s browser can.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <Doors />
        {tools.length === 0 && <p className="text-sm text-muted-foreground">agent-service is not reachable right now.</p>}
        <ul className="grid gap-2 sm:grid-cols-2">
          {tools.map((tool) => {
            const Icon = TOOL_ICON[tool.name] ?? Wrench
            return (
              <li key={tool.name} className="flex gap-3 rounded-lg border border-border p-3" title={tool.description}>
                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <Icon className="size-4" />
                </span>
                <span className="min-w-0">
                  <span className="block font-mono text-[11px] font-medium">{tool.name}</span>
                  <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">{tool.description}</span>
                </span>
              </li>
            )
          })}
        </ul>

        {guide ? (
          <ConnectorInstall guide={guide} fallbackUrl={mcpUrl} />
        ) : (
          mcpUrl && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 p-3">
              <span className="text-xs tracking-[0.12em] text-muted-foreground uppercase">MCP endpoint</span>
              <code className="min-w-0 flex-1 truncate font-mono text-xs">{mcpUrl}</code>
            </div>
          )
        )}
      </CardContent>
    </Card>
  )
}
