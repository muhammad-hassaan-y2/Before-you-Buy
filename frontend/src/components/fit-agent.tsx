"use client"

import { Bot, CircleSlash, ImageIcon, Loader2, Send, Sparkles, UserCheck, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { AgentRunTrace, RunStatusBadge } from "@/components/agent-run-trace"
import { AddToBag } from "@/components/bag-drawer"
import { FitViews } from "@/components/fit-views"
import { DimensionEstimateWarning, ProductSourceBadge } from "@/components/product-provenance"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { pollRun, startJourney, type AgentRun } from "@/lib/agent"
import { fetchSimulation, ROOM_SCAN_LABEL, uploadRoomPhoto, type Simulation } from "@/lib/api"
import { cn } from "@/lib/utils"

const EXAMPLES = [
  "Three-seater linen sofa under 900 for a living room, needs to leave a walkway to the balcony",
  "Wardrobe with two sliding doors, max 600, bedroom is narrow",
  "Corner desk under 400 that still lets the door swing open",
]

export function FitAgent() {
  const [brief, setBrief] = useState(EXAMPLES[0])
  const [width, setWidth] = useState("4.0")
  const [depth, setDepth] = useState("3.5")
  const [height, setHeight] = useState("2.4")
  const [photo, setPhoto] = useState<File | null>(null)
  const [run, setRun] = useState<AgentRun | null>(null)
  const [fit, setFit] = useState<{ id: string; detail: Simulation } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const fittedId = run?.decision?.simulation_id ?? null

  useEffect(() => {
    if (!fittedId) return
    // The recommendation is only worth the room it was measured in, so show that fit's own report.
    let live = true
    fetchSimulation(fittedId).then(
      (detail) => live && setFit({ id: fittedId, detail }),
      () => live && setFit(null),
    )
    return () => {
      live = false
    }
  }, [fittedId])

  const fitted = fit?.id === fittedId ? fit.detail : null

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (brief.trim().length < 3) {
      setError("Describe what you are looking for, in your own words.")
      return
    }
    controller.current?.abort()
    setBusy(true)
    setError(null)
    setRun(null)
    setFit(null)
    try {
      const imageKey = photo ? await uploadRoomPhoto(photo) : undefined
      const accepted = await startJourney({
        brief: brief.trim(),
        roomWidthM: Number(width),
        roomDepthM: Number(depth),
        roomHeightM: Number(height),
        imageKey,
      })
      const settled = await pollRun(accepted.run_id, setRun, { signal: controller.current?.signal })
      if (settled?.status === "running") setError("The agent is still working. Try again in a moment.")
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  const decision = run?.decision ?? null
  const handoff = decision?.action === "handoff" || run?.status === "awaiting_human"

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-start">
      <Card className="shadow-lg shadow-black/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="size-4 text-primary" /> Ask the fit agent
          </CardTitle>
          <CardDescription>
            Say it the way you would to a shop assistant. The agent reads your words, shortlists the catalog, runs a real
            fit simulation on each candidate and only then recommends. Attach a photo of the room and every candidate is
            measured against the room in it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="brief">Your brief</Label>
              <Textarea
                id="brief"
                rows={4}
                value={brief}
                onChange={(event) => setBrief(event.target.value)}
                placeholder="A sofa that seats three, under 900, and leaves a walkway to the balcony"
                disabled={busy}
              />
            </div>

            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES.map((example, index) => (
                <Button
                  key={example}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  disabled={busy}
                  onClick={() => setBrief(EXAMPLES[index])}
                >
                  <Sparkles className="size-3" /> Example {index + 1}
                </Button>
              ))}
            </div>

            <div className="space-y-2">
              <Label htmlFor="agent-photo">
                <ImageIcon className="size-3.5" /> Photo of the room (optional)
              </Label>
              <label
                htmlFor="agent-photo"
                className={cn(
                  "flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-dashed px-3 py-3 text-sm transition-colors",
                  photo ? "border-primary/60 bg-primary/5" : "hover:border-ring hover:bg-muted/40",
                )}
              >
                <span className="truncate text-muted-foreground">
                  {photo ? photo.name : "Drop or choose a JPG/PNG of the room"}
                </span>
                <input
                  id="agent-photo"
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  disabled={busy}
                  onChange={(event) => setPhoto(event.target.files?.[0] ?? null)}
                />
              </label>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  {photo
                    ? "Every candidate is fitted into the room measured from this photo, not the numbers below."
                    : "Without a photo the agent uses the room you type."}
                </p>
                {photo && (
                  <Button type="button" variant="ghost" size="sm" onClick={() => setPhoto(null)}>
                    <X className="size-3.5" /> Remove
                  </Button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {(
                [
                  ["Width", width, setWidth],
                  ["Depth", depth, setDepth],
                  ["Height", height, setHeight],
                ] as const
              ).map(([labelText, value, setter]) => (
                <div key={labelText} className="space-y-2">
                  <Label htmlFor={`agent-${labelText.toLowerCase()}`} className="text-muted-foreground">
                    {labelText} (m)
                  </Label>
                  <Input
                    id={`agent-${labelText.toLowerCase()}`}
                    inputMode="decimal"
                    value={value}
                    onChange={(event) => setter(event.target.value)}
                    disabled={busy}
                  />
                </div>
              ))}
            </div>

            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? <Loader2 className="animate-spin" /> : <Send className="size-4" />}
              {busy ? "Agent is working…" : "Find what fits"}
            </Button>
          </form>

          {run?.brief && (
            <div className="mt-5 rounded-lg border bg-muted/30 p-3 text-sm">
              <p className="text-xs tracking-[0.12em] text-muted-foreground uppercase">What the agent heard</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {run.brief.category && <Badge variant="outline">{run.brief.category}</Badge>}
                {run.brief.price_band && <Badge variant="secondary">{run.brief.price_band}</Badge>}
                {run.brief.budget_eur && <Badge variant="secondary">≤ {run.brief.budget_eur.toFixed(0)}</Badge>}
                {run.brief.must_haves.map((need) => (
                  <Badge key={need} variant="outline">
                    {need}
                  </Badge>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Read by {run.brief.source} · confidence {(run.brief.confidence * 100).toFixed(0)} %
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="shadow-lg shadow-black/5">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <CardTitle>How it was decided</CardTitle>
              <CardDescription className="mt-1">
                {run ? `Run ${run.id}` : "Every step records which model or endpoint drove it, so the answer can be audited."}
              </CardDescription>
            </div>
            {run && <RunStatusBadge status={run.status} />}
          </div>
        </CardHeader>

        <CardContent className="space-y-5">
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <CircleSlash className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!run && !error && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-sm text-muted-foreground">
              <Bot className="size-6 opacity-40" />
              No journey yet.
            </div>
          )}

          {run && <AgentRunTrace run={run} />}

          {run?.reply && (
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm leading-relaxed">{run.reply}</div>
          )}

          {decision && !handoff && (
            <div className="rounded-lg border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="success">{decision.action}</Badge>
                <span className="font-mono text-xs">{decision.sku ?? "—"}</span>
                <span className="ml-auto text-xs text-muted-foreground">confidence {(decision.confidence * 100).toFixed(0)} %</span>
              </div>
              {decision.reason && <p className="mt-2 text-muted-foreground">{decision.reason}</p>}
              {decision.simulation_id && (
                <p className="mt-1 font-mono text-xs text-muted-foreground">fit run {decision.simulation_id}</p>
              )}
              {/* The agent's own recommendation goes in the same bag a shopper fills by hand, with
                  the simulation that earned it - one door, whichever side asked. */}
              {decision.sku && decision.simulation_id && (
                <div className="mt-3 flex items-center justify-between gap-3">
                  <a
                    className="font-mono text-xs text-primary underline underline-offset-4"
                    href={`/api/v1/simulations/${decision.simulation_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    fit evidence
                  </a>
                  <AddToBag
                    sku={decision.sku}
                    simulationId={decision.simulation_id}
                    room={{ width_m: Number(width) || 4, depth_m: Number(depth) || 3.5, height_m: Number(height) || 2.4 }}
                    label="Bag the recommendation"
                  />
                </div>
              )}
            </div>
          )}

          {fitted?.fit_report && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{ROOM_SCAN_LABEL[fitted.room_scan?.method ?? "declared"]}</Badge>
                {fitted.product_profile && <ProductSourceBadge profile={fitted.product_profile} />}
                {fitted.product_profile && <DimensionEstimateWarning profile={fitted.product_profile} compact />}
              </div>
              <FitViews
                report={fitted.fit_report}
                widthM={fitted.room_scan?.width_m ?? fitted.room_width_m}
                depthM={fitted.room_scan?.depth_m ?? fitted.room_depth_m}
                obstacles={fitted.room_scan?.obstacles ?? fitted.fit_report.obstacles}
                scene={fitted.scene ?? null}
              />
            </div>
          )}

          {handoff && (
            <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
              <p className="flex items-center gap-2 font-medium">
                <UserCheck className="size-4" /> A person takes it from here
              </p>
              {decision?.reason && <p className="mt-1.5 text-muted-foreground">{decision.reason}</p>}
            </div>
          )}

          {run?.error && <p className="text-xs text-destructive">{run.error}</p>}
        </CardContent>
      </Card>
    </div>
  )
}
