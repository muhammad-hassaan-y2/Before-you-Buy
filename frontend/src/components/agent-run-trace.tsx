"use client"

import { Bot, Camera, Check, CircleSlash, GitBranch, Layers, Loader2, MessagesSquare, Search, SkipForward, Globe, Ruler, Wrench } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { runCost, type AgentRun, type AgentStep } from "@/lib/agent"

const KIND: Record<string, { label: string; icon: typeof Bot }> = {
  intake: { label: "Shopper brief received", icon: MessagesSquare },
  agent: { label: "Evolus agent told about the case", icon: Bot },
  brief: { label: "Brief read", icon: Search },
  room: { label: "Room measured from the photo", icon: Camera },
  shortlist: { label: "Catalog shortlisted", icon: Layers },
  simulate: { label: "Fit simulations", icon: Ruler },
  fit: { label: "Fit report", icon: Check },
  branch: { label: "Decision", icon: GitBranch },
  compare: { label: "Candidates compared", icon: Check },
  reply: { label: "Reply drafted", icon: MessagesSquare },
  handoff: { label: "Handed to a person", icon: CircleSlash },
}

const VERDICT: Record<string, "success" | "warning" | "destructive" | "secondary"> = {
  fits: "success",
  tight: "warning",
  too_large: "destructive",
  blocked: "destructive",
}

const VERDICT_LABEL: Record<string, string> = {
  fits: "fits",
  tight: "tight",
  too_large: "too large",
  blocked: "blocked",
}

/** The agent's own transcript: which step ran, what drove it, how long it took. */
export function AgentRunTrace({ run }: { run: AgentRun }) {
  const passes = [...new Set(run.steps.map((step) => step.iteration))]
  return (
    <div className="space-y-4">
      <RunCostStrip run={run} />
      {passes.map((pass) => (
        <div key={pass} className="space-y-2">
          {passes.length > 1 && (
            <p className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">Pass {pass}</p>
          )}
          <ol className="space-y-1.5">
            {run.steps
              .filter((step) => step.iteration === pass)
              .map((step) => (
                <TraceRow key={step.index} step={step} />
              ))}
          </ol>
        </div>
      ))}

      {run.attempts.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">Tested against this room</p>
          {run.attempts.map((attempt) => (
            <div key={attempt.sku} className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-sm">
              <Badge variant={VERDICT[attempt.verdict ?? ""] ?? "secondary"}>{VERDICT_LABEL[attempt.verdict ?? ""] ?? attempt.verdict ?? attempt.status}</Badge>
              <span className="font-medium">{attempt.name}</span>
              <span className="text-xs text-muted-foreground">{attempt.price_band ?? "—"}</span>
              {attempt.verdict && (
                <span className="ml-auto font-mono text-xs tabular-nums text-muted-foreground">
                  {attempt.coverage_pct.toFixed(1)} % floor · {tightest(attempt.walkway_m)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/** What the journey spent, read off its own trace. The verdicts are not token spend: every one
 *  of them came out of the geometry worker, so the only calls a model took are counted here. */
export function RunCostStrip({ run }: { run: AgentRun }) {
  const cost = runCost(run)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
      <span className="font-mono tabular-nums">{duration(cost.total_ms)} measured</span>
      <span className="font-mono tabular-nums">
        {cost.fits} {cost.fits === 1 ? "fit" : "fits"} by the geometry worker
      </span>
      <span className="font-mono tabular-nums">
        {cost.model_calls} model call{cost.model_calls === 1 ? "" : "s"}
      </span>
      <span className="font-mono tabular-nums">
        {cost.passes} search pass{cost.passes === 1 ? "" : "es"}
      </span>
      {cost.slowest && <span className="font-mono">slowest {cost.slowest.label} · {cost.slowest.ms} ms</span>}
      {run.evolus_execution_id && (
        <Badge variant="outline" className="ml-auto font-mono text-[10px]">
          evolus {run.evolus_execution_id}
        </Badge>
      )}
    </div>
  )
}

function duration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function TraceRow({ step }: { step: AgentStep }) {
  const meta = KIND[step.kind] ?? { label: step.kind, icon: Wrench }
  const Icon = meta.icon
  return (
    <li className={cn("flex items-start gap-3 rounded-lg border px-3 py-2 text-sm", step.status === "failed" && "border-destructive/40 bg-destructive/5")}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", step.status === "skipped" ? "text-muted-foreground/50" : step.status === "failed" ? "text-destructive" : "text-primary")} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">
          {meta.label}
          {step.group && <span className="ml-2 text-xs font-normal text-muted-foreground">{step.group} · parallel</span>}
        </p>
        {step.detail && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.detail}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2 text-[11px] text-muted-foreground">
        {step.tool && (
          <span className="flex items-center gap-1 font-mono">
            {step.tool.includes("evolus") || step.tool.startsWith("POST") || step.tool.startsWith("GET") ? <Globe className="size-3" /> : <Wrench className="size-3" />}
            {step.tool}
          </span>
        )}
        {step.status === "skipped" && <SkipForward className="size-3" />}
        {step.ms > 0 && <span className="font-mono tabular-nums">{step.ms} ms</span>}
      </div>
    </li>
  )
}

function tightest(walkway: Record<string, number>): string {
  const values = Object.values(walkway)
  if (values.length === 0) return "no walkway reported"
  const min = Math.min(...values)
  return `${min.toFixed(2)} m walkway`
}

export function RunStatusBadge({ status }: { status: AgentRun["status"] }) {
  if (status === "running") {
    return (
      <Badge variant="outline" className="gap-1.5">
        <Loader2 className="size-3 animate-spin" /> working
      </Badge>
    )
  }
  if (status === "awaiting_human") return <Badge variant="warning">awaiting a person</Badge>
  if (status === "failed") return <Badge variant="destructive">failed</Badge>
  return <Badge variant="success">done</Badge>
}
