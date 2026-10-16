"use client"

import { Check, Copy, Wrench } from "lucide-react"
import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { fetchTools, type ToolSpec } from "@/lib/agent"

/** The capability surface an Evolus agent, a workflow step or an MCP client is handed. */
export function AgentSurface() {
  const [tools, setTools] = useState<ToolSpec[]>([])
  const [copied, setCopied] = useState(false)
  const [mcpUrl, setMcpUrl] = useState("")

  useEffect(() => {
    fetchTools().then(setTools, () => setTools([]))
    // Evolus reaches a tunnel host over https; localhost stays as it is.
    const origin = window.location.origin
    const host = window.location.hostname
    const secure = origin.startsWith("https:") || (origin.startsWith("http:") && !["localhost", "127.0.0.1", "::1"].includes(host))
    setMcpUrl(`${secure ? origin.replace(/^http:/, "https:") : origin}/mcp/`)
  }, [])

  async function copy() {
    try {
      await navigator.clipboard.writeText(mcpUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Card className="shadow-lg shadow-black/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="size-4 text-primary" /> What the agent is allowed to do
        </CardTitle>
        <CardDescription>
          Same seven capabilities over three doors: the MCP connector for the agent, REST for an Evolus workflow step, and
          this page. The agent can only ever do what a shopper's browser can do.
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

        {mcpUrl && (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 p-3">
            <span className="text-xs tracking-[0.12em] text-muted-foreground uppercase">MCP endpoint</span>
            <code className="min-w-0 flex-1 truncate font-mono text-xs">{mcpUrl}</code>
            <Button type="button" variant="outline" size="sm" onClick={copy}>
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
