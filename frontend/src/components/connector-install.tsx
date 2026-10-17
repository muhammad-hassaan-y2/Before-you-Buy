"use client"

import { Check, Copy, Globe, ShieldAlert } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ConnectGuide } from "@/lib/agent"

/** The order a reader is most likely to want, not the order the service happened to list. */
const ORDER = ["chatgpt", "claude", "claude-code", "cursor", "evolus"]

type Props = {
  guide: ConnectGuide
  /** What this page can actually reach, which is not always the service's own URL. */
  fallbackUrl: string
}

/** The connector as a thing a person can add: the URL, the auth it really expects, and the steps
 *  for the assistant they are standing in front of. */
export function ConnectorInstall({ guide, fallbackUrl }: Props) {
  const keys = ORDER.filter((key) => guide.clients[key]).concat(Object.keys(guide.clients).filter((key) => !ORDER.includes(key)))
  const [client, setClient] = useState(keys[0] ?? "chatgpt")
  const [copied, setCopied] = useState("")
  const shown = guide.clients[client]
  const url = guide.public ? guide.url : fallbackUrl

  async function copy(label: string, text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(label)
      setTimeout(() => setCopied(""), 1800)
    } catch {
      setCopied("")
    }
  }

  return (
    <div className="space-y-3 rounded-lg border bg-muted/30 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs tracking-[0.12em] text-muted-foreground uppercase">Add the connector</span>
        <code className="min-w-0 flex-1 truncate font-mono text-xs">{url}</code>
        <Button type="button" variant="outline" size="sm" onClick={() => copy("url", url)}>
          {copied === "url" ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied === "url" ? "Copied" : "Copy URL"}
        </Button>
      </div>

      <div role="group" aria-label="Which assistant" className="flex flex-wrap gap-1.5">
        {keys.map((key) => (
          <Button
            key={key}
            type="button"
            size="sm"
            variant={client === key ? "default" : "outline"}
            aria-pressed={client === key}
            onClick={() => setClient(key)}
          >
            {guide.clients[key]?.label ?? key}
          </Button>
        ))}
      </div>

      {shown && (
        <div className="space-y-2 text-sm">
          <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
            {shown.steps?.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          {shown.command && (
            <div className="flex flex-wrap items-center gap-2 rounded-md border bg-background p-2">
              <code className="min-w-0 flex-1 break-all font-mono text-[11px]">{shown.command}</code>
              <Button type="button" variant="ghost" size="sm" onClick={() => copy("command", shown.command ?? "")}>
                {copied === "command" ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                Copy
              </Button>
            </div>
          )}
          {shown.config && (
            <pre className="overflow-x-auto rounded-md border bg-background p-2 font-mono text-[11px]">
              {JSON.stringify(shown.config, null, 2)}
            </pre>
          )}
          {shown.note && <p className="text-xs text-muted-foreground">{shown.note}</p>}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant={guide.auth.type === "none" ? "secondary" : "outline"}>{guide.auth.type === "none" ? "No authentication" : "Bearer key"}</Badge>
        <span className="min-w-0 flex-1 text-muted-foreground">{guide.auth.why}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant="outline">{guide.transport}</Badge>
        <Badge variant="outline">{guide.mode}</Badge>
        <Badge variant="outline">{guide.capabilities.tools.length} tools</Badge>
        <Badge variant="outline">{guide.capabilities.resources.length} resources</Badge>
        <Badge variant="outline">{guide.capabilities.prompts.length} prompts</Badge>
      </div>

      {!guide.public && (
        <p className="flex items-start gap-2 text-xs text-muted-foreground">
          <Globe className="mt-0.5 size-3.5 shrink-0" />
          This run has no public address, so the URL above only works on this machine. ChatGPT and Claude add connectors over https:
          set <code className="font-mono">PUBLIC_BASE_URL</code> to your tunnel and reload.
        </p>
      )}
      {guide.auth.type !== "none" && (guide.auth.does_not_work_in.includes("chatgpt") || guide.auth.does_not_work_in.includes("claude.ai")) && (
        <p className="flex items-start gap-2 text-xs text-muted-foreground">
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" />
          A keyed connector is a Claude Code or Cursor connector. {guide.auth.does_not_work_in.join(", ")} sends no static header, so it
          needs this door open or an OAuth server in front of it.
        </p>
      )}
    </div>
  )
}
