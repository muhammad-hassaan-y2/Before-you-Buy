"use client"

import { Box, CheckCircle2, Eye, Layers, RotateCcw, Scan, XCircle } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { SceneSpec } from "@/lib/api"
import { RoomEngine } from "@/lib/scene-engine"

const VERDICT: Record<string, { label: string; variant: "success" | "warning" | "destructive" }> = {
  fits: { label: "Fits with room to move", variant: "success" },
  tight: { label: "Fits, but tight", variant: "warning" },
  too_large: { label: "Too large for this room", variant: "destructive" },
  blocked: { label: "No clear placement", variant: "destructive" },
}

/** The 3D viewport. It draws what the pipeline measured - the placement, its walkways and the
 *  clearance the geometry worker insisted on - and never invents a fit of its own. */
export function SceneViewer({ spec, className }: { spec: SceneSpec | null; className?: string }) {
  const canvas = useRef<HTMLCanvasElement | null>(null)
  const engine = useRef<RoomEngine | null>(null)
  const [placement, setPlacement] = useState<string | null>(null)
  const [view, setView] = useState<string | null>(null)
  const [envelope, setEnvelope] = useState(true)
  const [failed, setFailed] = useState(false)

  const hasScene = spec !== null
  const latest = useRef<SceneSpec | null>(spec)
  latest.current = spec

  // The canvas only exists once there is a scene to draw, so the engine is built when that flips.
  useEffect(() => {
    if (!canvas.current) return
    try {
      engine.current = new RoomEngine(canvas.current, latest.current)
    } catch {
      setFailed(true)
    }
    return () => {
      engine.current?.dispose()
      engine.current = null
    }
  }, [hasScene])

  useEffect(() => {
    if (!spec || !engine.current) return
    engine.current.setSpec(spec)
    const preferred = spec.placements.find((spot) => spot.label === placement) ?? null
    const spot = preferred ?? spec.placements.find((candidate) => candidate.fits) ?? spec.placements[0] ?? null
    setPlacement(spot?.label ?? null)
    engine.current.showPlacement(spot?.label ?? null)
    engine.current.toggleEnvelope(envelope)
  }, [spec, envelope])

  useEffect(() => {
    engine.current?.showPlacement(placement)
  }, [placement])

  const active = spec?.placements.find((spot) => spot.label === placement) ?? null
  const walkways = active ? Object.entries(active.walkway_m) : []

  if (!spec) {
    return (
      <div className={cn("flex min-h-40 items-center justify-center gap-2 rounded-lg border border-dashed bg-[#0f0d0c]/5 text-sm text-muted-foreground", className)}>
        <Box className="size-6 opacity-50" />
        Nothing to place yet.
      </div>
    )
  }

  if (failed) {
    return (
      <div className={cn("flex min-h-40 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground", className)}>
        This browser could not open WebGL, so the plan view below is what you get.
      </div>
    )
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="relative overflow-hidden rounded-lg border bg-[#0f0d0c]">
        <canvas ref={canvas} className="block h-[340px] w-full lg:h-[420px]" />

        <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-wrap items-center gap-2 p-3">
          <Badge variant={VERDICT[spec.verdict]?.variant ?? "secondary"}>{VERDICT[spec.verdict]?.label ?? spec.verdict}</Badge>
          <Badge variant="outline">{spec.product_name}</Badge>
          <Badge variant="secondary">
            {spec.geometry.width_cm.toFixed(0)} × {spec.geometry.depth_cm.toFixed(0)} × {spec.geometry.height_cm.toFixed(0)} cm
          </Badge>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {spec.cameras.map((camera) => (
          <Button key={camera.label} type="button" size="sm" variant={view === camera.label ? "default" : "outline"} onClick={() => { setView(camera.label); engine.current?.setCamera(camera.label) }}>
            <Eye className="size-3.5" /> {camera.label}
          </Button>
        ))}
        <Button type="button" size="sm" variant="ghost" onClick={() => { setView(null); engine.current?.setCamera(null) }}>
          <RotateCcw className="size-3.5" /> Reset view
        </Button>
        <Button
          type="button"
          size="sm"
          variant={envelope ? "default" : "outline"}
          onClick={() => {
            const next = !envelope
            setEnvelope(next)
            engine.current?.toggleEnvelope(next)
          }}
        >
          <Scan className="size-3.5" /> Clearance
        </Button>
      </div>

      {spec.placements.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {spec.placements.map((spot) => (
            <Button
              key={spot.label}
              type="button"
              size="sm"
              variant={spot.label === placement ? "default" : "outline"}
              onClick={() => setPlacement(spot.label)}
            >
              {spot.fits ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
              {spot.label}
            </Button>
          ))}
        </div>
      )}

      {active && walkways.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Layers className="size-3.5" /> walkways at {active.label}
          </span>
          {walkways.map(([face, gap]) => (
            <span key={face} className="font-mono tabular-nums">
              {face} {gap.toFixed(2)} m
            </span>
          ))}
          <span className="ml-auto font-mono tabular-nums">floor used {spec.coverage_pct.toFixed(1)} %</span>
        </div>
      )}
    </div>
  )
}
