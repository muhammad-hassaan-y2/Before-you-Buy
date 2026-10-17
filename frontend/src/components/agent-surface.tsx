"use client"

import { Wrench } from "lucide-react"
import { useEffect, useState } from "react"

import { ConnectorInstall } from "@/components/connector-install"
import { Badge } from "@/components/ui/badge"
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
    <Card className="shadow-lg shadow-black/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="size-4 text-primary" /> What the agent is allowed to do
        </CardTitle>
        <CardDescription>
          Every capability is the same function behind three doors: the MCP connector for the agent, REST for an Evolus
          workflow step, and this page. The agent can only ever do what a shopper&apos;s browser can do.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {tools.length === 0 && <p className="text-sm text-muted-foreground">agent-service is not reachable right now.</p>}
        <ul className="space-y-2 text-sm">
          {tools.map((tool) => (
            <li key={tool.name} className="flex flex-wrap items-baseline gap-2">
              <Badge variant="outline" className="font-mono text-[11px]">
                {tool.name}
              </Badge>
              <span className="min-w-0 flex-1 text-muted-foreground">{tool.description}</span>
            </li>
          ))}
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
