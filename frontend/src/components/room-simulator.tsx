"use client"

import { AlertTriangle, ImageIcon, Link2, Loader2, Ruler, Sofa, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { FitResult, ProgressStrip, STEPS } from "@/components/fit-result"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createSimulation, pollSimulation, type Simulation } from "@/lib/api"
import { cn } from "@/lib/utils"

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
  const stepIndex = simulation ? STEPS.findIndex((step) => step.key === simulation.status) : busy ? 0 : -1

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <Card className="shadow-lg shadow-black/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sofa className="size-4 text-primary" /> What are you considering?
          </CardTitle>
          <CardDescription>
            Paste a product link and the inference service reads its real dimensions with AMD Token Factory. Or attach a
            room photo and describe the piece.
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
            {stepIndex >= 0 && !report ? STEPS[Math.min(stepIndex, STEPS.length - 1)].label + "…" : "Geometry from the Shapely worker."}
          </CardDescription>
          <ProgressStrip status={simulation?.status} started={busy} />
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

          {simulation && report && <FitResult simulation={simulation} placement={placement} onPlacement={setPlacement} />}
        </CardContent>
      </Card>
    </div>
  )
}
