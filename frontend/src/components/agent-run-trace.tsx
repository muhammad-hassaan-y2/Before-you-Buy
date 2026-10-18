"use client"

import { Bot, Camera, Check, CircleSlash, Cpu, GitBranch, Globe, Layers, Loader2, MessagesSquare, Repeat, Ruler, Search, Timer, Wrench } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Meter, PriceBand } from "@/components/visuals"
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

const VERDICT_LABEL: Record<string, string> = {
  fits: "fits",
  tight: "tight",
  too_large: "too large",
  blocked: "blocked",
}

const VERDICT_TONE: Record<string, "success" | "warning" | "destructive"> = {
  fits: "success",
  tight: "warning",
  too_large: "destructive",
  blocked: "destructive",
}

const TONE_TEXT = { success: "text-success", warning: "text-warning", destructive: "text-destructive" }
const TONE_BAR = { success: "bg-success", warning: "bg-warning", destructive: "bg-destructive" }

/** The agent's own transcript, drawn as a timeline: one node per step on a rail, each with a bar
 *  as long as the step took, so the slow part of the journey is the first thing you see. */
export function AgentRunTrace({ run }: { run: AgentRun }) {
  const passes = [...new Set(run.steps.map((step) => step.iteration))]
  const longest = Math.max(1, ...run.steps.map((step) => step.ms))
  return (
    <div className="space-y-6">
      <RunCostStrip run={run} />
      {passes.map((pass) => (
        <div key={pass}>
          {passes.length > 1 && <p className="eyebrow mb-3 text-muted-foreground">Pass {pass}</p>}
          <ol className="relative space-y-0 before:absolute before:top-3 before:bottom-3 before:left-[15px] before:w-px before:bg-border">
            {run.steps
              .filter((step) => step.iteration === pass)
              .map((step) => (
                <TraceRow key={step.index} step={step} longest={longest} />
              ))}
          </ol>
        </div>
      ))}

      {run.attempts.length > 0 && (
        <div>
          <p className="eyebrow mb-3 text-muted-foreground">Tested against this room</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {run.attempts.map((attempt) => {
              const tone = VERDICT_TONE[attempt.verdict ?? ""]
              const gaps = Object.values(attempt.walkway_m)
              const gap = gaps.length ? Math.min(...gaps) : null
              return (
                <div key={attempt.sku} className="rounded-lg border border-border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 truncate text-sm font-medium">{attempt.name}</p>
                    <PriceBand band={attempt.price_band} />
                  </div>
                  <p className={cn("mt-2 flex items-center gap-2 text-sm font-semibold", tone ? TONE_TEXT[tone] : "text-muted-foreground")}>
                    <span aria-hidden className={cn("size-2 rounded-full", tone ? TONE_BAR[tone] : "bg-muted-foreground")} />
                    {VERDICT_LABEL[attempt.verdict ?? ""] ?? attempt.verdict ?? attempt.status}
                  </p>
                  {attempt.verdict && (
                    <div className="mt-3 space-y-2.5">
                      <div>
                        <div className="num mb-1 flex justify-between text-[11px] text-muted-foreground">
                          <span>floor taken</span>
                          <span>{attempt.coverage_pct.toFixed(0)} %</span>
                        </div>
                        <Meter value={attempt.coverage_pct} label={`${attempt.coverage_pct.toFixed(0)} percent of the floor taken`} />
                      </div>
                      {gap !== null && (
                        <div>
                          <div className="num mb-1 flex justify-between text-[11px] text-muted-foreground">
                            <span>tightest walkway</span>
                            <span>{gap.toFixed(2)} m</span>
                          </div>
                          <div className="relative">
                            <Meter value={gap} max={1.2} tone={gap >= 0.6 ? "success" : "warning"} label={`Tightest walkway ${gap.toFixed(2)} metres`} />
                            <span aria-hidden className="absolute -top-0.5 bottom-[-2px] left-1/2 w-px bg-foreground" />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

/** What the journey spent, read off its own trace, as four numbers you can compare at a glance.
 *  The verdicts are not token spend: every one came out of the geometry worker, so the only calls
 *  a model took are the ones counted here. */
export function RunCostStrip({ run }: { run: AgentRun }) {
  const cost = runCost(run)
  const tiles = [
    { icon: Timer, value: duration(cost.total_ms), label: "measured" },
    { icon: Ruler, value: String(cost.fits), label: cost.fits === 1 ? "fit by the worker" : "fits by the worker" },
    { icon: Cpu, value: String(cost.model_calls), label: cost.model_calls === 1 ? "model call" : "model calls" },
    { icon: Repeat, value: String(cost.passes), label: cost.passes === 1 ? "search pass" : "search passes" },
  ]
  return (
    <div>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-4">
        {tiles.map(({ icon: Icon, value, label }) => (
          <div key={label} className="bg-card p-3">
            <Icon className="size-4 text-primary" />
            <p className="num display mt-2 text-2xl">{value}</p>
            <p className="text-[11px] text-muted-foreground">{label}</p>
          </div>
        ))}
      </div>
      {(cost.slowest || run.evolus_execution_id) && (
        <p className="mt-2 flex flex-wrap items-center gap-x-4 text-[11px] text-muted-foreground">
          {cost.slowest && <span className="font-mono">slowest · {cost.slowest.label} · {cost.slowest.ms} ms</span>}
          {run.evolus_execution_id && <span className="font-mono">evolus {run.evolus_execution_id}</span>}
        </p>
      )}
    </div>
  )
}

function duration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function TraceRow({ step, longest }: { step: AgentStep; longest: number }) {
  const meta = KIND[step.kind] ?? { label: step.kind, icon: Wrench }
  const Icon = meta.icon
  const failed = step.status === "failed"
  const skipped = step.status === "skipped"
  return (
    <li className="relative flex items-start gap-3 py-2">
      <span
        className={cn(
          "relative z-10 flex size-[31px] shrink-0 items-center justify-center rounded-full border bg-card",
          failed ? "border-destructive text-destructive" : skipped ? "border-border text-muted-foreground/60" : "border-primary/60 text-primary",
        )}
      >
        <Icon className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1 pt-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <p className={cn("text-sm font-medium", skipped && "text-muted-foreground line-through decoration-1")}>{meta.label}</p>
          {step.group && <span className="text-[11px] text-muted-foreground">{step.group} · parallel</span>}
          {step.tool && (
            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
              {step.tool.includes("evolus") || step.tool.startsWith("POST") || step.tool.startsWith("GET") ? <Globe className="size-3" /> : <Wrench className="size-3" />}
              {step.tool}
            </span>
          )}
        </div>
        {step.ms > 0 && (
          <div className="mt-1.5 flex items-center gap-2">
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <span className={cn("block h-full rounded-full", failed ? "bg-destructive" : "bg-primary/70")} style={{ width: `${Math.max(3, (step.ms / longest) * 100)}%` }} />
            </span>
            <span className="num w-16 text-right text-[11px] text-muted-foreground">{step.ms} ms</span>
          </div>
        )}
        {step.detail && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{step.detail}</p>}
      </div>
    </li>
  )
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
