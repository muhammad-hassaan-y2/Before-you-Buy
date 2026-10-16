"use client"

import { AlertTriangle, CheckCircle2, ImageIcon, Link2, Loader2, Ruler, Sofa, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { RoomPlan } from "@/components/room-plan"
import { SceneViewer } from "@/components/scene-viewer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createSimulation, pollSimulation, type Simulation } from "@/lib/api"
import { cn } from "@/lib/utils"

const STEPS = [
  { key: "pending", label: "Queued" },
  { key: "cataloguing", label: "Matching the SKU" },
  { key: "enriching", label: "Reading the listing" },
  { key: "scanning", label: "Measuring the room" },
  { key: "fitting", label: "Fitting the floor plan" },
  { key: "completed", label: "Ready" },
] as const

const PRODUCT_SOURCE: Record<string, string> = {
  vllm: "vLLM",
  catalog: "Catalog SKU",
  heuristic: "Category heuristics",
}

const SCAN_LABEL: Record<string, string> = {
  photo: "Room measured from the photo",
  "photo-ignored": "Photo unreadable — using your numbers",
  declared: "Using your numbers",
}

const VERDICT: Record<string, { label: string; variant: "success" | "warning" | "destructive" }> = {
  fits: { label: "Fits with room to move", variant: "success" },
  tight: { label: "Fits, but tight", variant: "warning" },
  too_large: { label: "Too large for this room", variant: "destructive" },
  blocked: { label: "No clear placement", variant: "destructive" },
}

export function RoomSimulator() {
  const [link, setLink] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [width, setWidth] = useState("4.0")
  const [depth, setDepth] = useState("3.5")
  const [height, setHeight] = useState("2.4")
  const [notes, setNotes] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [placement, setPlacement] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!link.trim() && !file) {
      setError("Paste a product link or attach a room photo first.")
      return
    }
    controller.current?.abort()
    setBusy(true)
    setError(null)
    setSimulation(null)
    setPlacement(null)
    try {
      const accepted = await createSimulation({
        link: link.trim() || undefined,
        file,
        roomWidthM: Number(width),
        roomDepthM: Number(depth),
        roomHeightM: Number(height),
        notes: notes.trim() || undefined,
      })
      const settled = await pollSimulation(accepted.id, setSimulation, { signal: controller.current?.signal })
      if (settled && settled.status !== "completed") {
        setError(settled.error ?? "The workers did not finish in time. Check the service logs.")
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  const report = simulation?.fit_report ?? null
  const profile = simulation?.product_profile ?? null
  const scan = simulation?.room_scan ?? null
  // Geometry measures the scanned room, which is the shopper's own when the photo could not be read.
  const roomWidth = scan?.width_m ?? simulation?.room_width_m ?? 4
  const roomDepth = scan?.depth_m ?? simulation?.room_depth_m ?? 3.5
  const activeSpot = report?.placements.find((spot) => spot.label === placement) ?? null
  const stepIndex = simulation ? STEPS.findIndex((step) => step.key === simulation.status) : busy ? 0 : -1

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <Card className="shadow-lg shadow-black/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sofa className="size-4 text-primary" /> What are you considering?
          </CardTitle>
          <CardDescription>
            Paste a product link and the inference service asks vLLM for its real dimensions. Or attach a room photo and
            describe the piece.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="link">
                <Link2 className="size-3.5" /> Product link
              </Label>
              <Input
                id="link"
                value={link}
                onChange={(event) => setLink(event.target.value)}
                placeholder="https://www.ikea.com/.../sofa"
                disabled={busy}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="photo">
                <ImageIcon className="size-3.5" /> Room photo (optional)
              </Label>
              <label
                htmlFor="photo"
                className={cn(
                  "flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-dashed px-3 py-3 text-sm transition-colors",
                  file ? "border-primary/60 bg-primary/5" : "hover:border-ring hover:bg-muted/40",
                )}
              >
                <span className="truncate text-muted-foreground">{file ? file.name : "Drop or choose a JPG/PNG"}</span>
                <input
                  id="photo"
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </label>
              {file && (
                <Button type="button" variant="ghost" size="sm" onClick={() => setFile(null)}>
                  <X className="size-3.5" /> Remove
                </Button>
              )}
            </div>

            <div className="grid grid-cols-3 gap-3">
              {([
                ["Width", width, setWidth],
                ["Depth", depth, setDepth],
                ["Height", height, setHeight],
              ] as const).map(([labelText, value, setter]) => (
                <div key={labelText} className="space-y-2">
                  <Label htmlFor={labelText.toLowerCase()} className="text-muted-foreground">
                    {labelText} (m)
                  </Label>
                  <Input
                    id={labelText.toLowerCase()}
                    inputMode="decimal"
                    value={value}
                    onChange={(event) => setter(event.target.value)}
                    disabled={busy}
                  />
                </div>
              ))}
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes" className="text-muted-foreground">
                Notes for the model
              </Label>
              <Input
                id="notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="three-seater linen sofa, oak legs"
                disabled={busy}
              />
            </div>

            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? <Loader2 className="animate-spin" /> : <Ruler className="size-4" />}
              {busy ? "Running simulation…" : "Simulate in my room"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card className="shadow-lg shadow-black/5">
        <CardHeader>
          <CardTitle>Result</CardTitle>
          <CardDescription>
            {stepIndex >= 0 && !report
              ? STEPS[Math.min(stepIndex, STEPS.length - 1)].label + "…"
              : "Geometry from the Shapely worker."}
          </CardDescription>
          {stepIndex >= 0 && (
            <ol className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              {STEPS.map((step, index) => (
                <li key={step.key} className="flex items-center gap-1.5">
                  <span
                    className={cn(
                      "size-1.5 rounded-full transition-colors",
                      index < stepIndex || simulation?.status === "completed"
                        ? "bg-success"
                        : index === stepIndex
                          ? "bg-primary animate-pulse"
                          : "bg-muted-foreground/30",
                    )}
                  />
                  {index > 0 && <span className="mr-1 h-px w-4 bg-border" />}
                  {step.label}
                </li>
              ))}
            </ol>
          )}
        </CardHeader>

        <CardContent className="space-y-5">
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!report && !error && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-sm text-muted-foreground">
              <Sofa className="size-6 opacity-40" />
              Nothing simulated yet.
            </div>
          )}

          {report && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={VERDICT[report.verdict]?.variant ?? "secondary"}>{VERDICT[report.verdict]?.label ?? report.verdict}</Badge>
                {profile && (
                  <Badge variant="outline">
                    {profile.geometry.width_cm.toFixed(0)} × {profile.geometry.depth_cm.toFixed(0)} × {profile.geometry.height_cm.toFixed(0)} cm
                  </Badge>
                )}
                {profile && <Badge variant="secondary">{PRODUCT_SOURCE[profile.source] ?? profile.source}</Badge>}
                {scan && <Badge variant="outline">{SCAN_LABEL[scan.method] ?? scan.method}</Badge>}
              </div>

              <div className="rounded-lg border bg-muted/30 p-3">
                <RoomPlan widthM={roomWidth} depthM={roomDepth} report={report} placement={activeSpot} obstacles={scan?.obstacles ?? report.obstacles} />
              </div>

              {simulation?.scene && (
                <div className="space-y-2">
                  <p className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">In the room, to scale</p>
                  <SceneViewer spec={simulation.scene} />
                </div>
              )}

              <dl className="grid grid-cols-3 gap-3 text-sm">
                {[
                  ["Room", `${report.room_area_m2.toFixed(1)} m²`],
                  ["Usable", `${report.usable_area_m2.toFixed(1)} m²`],
                  ["Occupied", `${report.coverage_pct.toFixed(1)} %`],
                ].map(([labelText, value]) => (
                  <div key={labelText} className="rounded-lg border p-3">
                    <dt className="text-xs text-muted-foreground">{labelText}</dt>
                    <dd className="font-mono text-base tabular-nums">{value}</dd>
                  </div>
                ))}
              </dl>

              {profile && (
                <div className="rounded-lg border p-3 text-sm">
                  <p className="font-medium">{profile.name}</p>
                  <p className="mt-1 text-muted-foreground">{profile.summary}</p>
                </div>
              )}

              {report.conflicts.length > 0 && (
                <ul className="space-y-1.5 text-sm">
                  {report.conflicts.map((conflict) => (
                    <li key={conflict} className="flex gap-2 text-muted-foreground">
                      <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" />
                      {conflict}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </CardContent>

        {report && report.placements.length > 0 && (
          <CardFooter className="border-t bg-muted/20">
            <div className="flex w-full flex-wrap gap-2">
              {report.placements.map((spot) => (
                <Button
                  key={spot.label}
                  type="button"
                  size="sm"
                  variant={activeSpot?.label === spot.label ? "default" : "outline"}
                  onClick={() => setPlacement(spot.label)}
                >
                  {spot.fits ? <CheckCircle2 className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
                  {spot.label}
                </Button>
              ))}
            </div>
          </CardFooter>
        )}
      </Card>
    </div>
  )
}
