"use client"

import { AlertTriangle, Box, Download, Loader2, Ruler, Sofa } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"

import { DeliveryPath } from "@/components/delivery-path"
import { DimensionEstimateWarning, ProductSourceBadge } from "@/components/product-provenance"
import { RoomPlan } from "@/components/room-plan"
import { SceneViewer } from "@/components/scene-viewer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { createSimulation, fetchCatalog, pollSimulation, type CatalogRow, type Simulation } from "@/lib/api"

const STAGES = [
  { key: "pending", label: "Queued" },
  { key: "cataloguing", label: "Matching the SKU" },
  { key: "enriching", label: "Reading the listing" },
  { key: "scanning", label: "Measuring the room" },
  { key: "fitting", label: "Fitting the floor plan" },
  { key: "rendering", label: "Building the scene" },
  { key: "completed", label: "Ready" },
] as const

/** The 3D workspace: pick a real SKU, give it a room, and stand it there before you buy. */
export function SceneWorkspace() {
  const [rows, setRows] = useState<CatalogRow[]>([])
  const [sku, setSku] = useState<string | null>(null)
  const [category, setCategory] = useState<string | null>(null)
  const [width, setWidth] = useState("4.0")
  const [depth, setDepth] = useState("3.5")
  const [height, setHeight] = useState("2.4")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => {
    fetchCatalog().then(setRows, () => setError("catalog-service is not reachable."))
    return () => controller.current?.abort()
  }, [])

  const categories = useMemo(() => [...new Set(rows.map((row) => row.category))].sort(), [rows])
  const shown = category ? rows.filter((row) => row.category === category) : rows
  const picked = rows.find((row) => row.sku === sku) ?? null
  const stage = simulation ? STAGES.findIndex((step) => step.key === simulation.status) : -1

  async function run() {
    if (!picked) {
      setError("Choose a piece from the catalog first.")
      return
    }
    controller.current?.abort()
    setBusy(true)
    setError(null)
    setSimulation(null)
    try {
      const accepted = await createSimulation({
        link: `https://shop.example.local/p/${picked.sku}`,
        notes: `${picked.name} ${picked.brand} ${picked.category}`,
        roomWidthM: Number(width),
        roomDepthM: Number(depth),
        roomHeightM: Number(height),
      })
      const settled = await pollSimulation(accepted.id, setSimulation, { signal: controller.current?.signal })
      if (settled && settled.status === "failed") setError(settled.error ?? "The workers failed on this one.")
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
      <div className="space-y-6">
        <Card className="shadow-lg shadow-black/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sofa className="size-4 text-primary" /> The shelf
            </CardTitle>
            <CardDescription>{rows.length} SKUs the catalog service knows about. Pick one and stand it in a room.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-1.5">
              <Button type="button" size="sm" variant={category === null ? "default" : "outline"} onClick={() => setCategory(null)}>
                All
              </Button>
              {categories.map((name) => (
                <Button key={name} type="button" size="sm" variant={category === name ? "default" : "outline"} onClick={() => setCategory(name)}>
                  {name}
                </Button>
              ))}
            </div>

            <ul className="max-h-80 space-y-1.5 overflow-y-auto pr-1">
              {shown.map((row) => (
                <li key={row.sku}>
                  <button
                    type="button"
                    onClick={() => setSku(row.sku)}
                    className={cn(
                      "w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                      sku === row.sku ? "border-primary/60 bg-primary/10" : "hover:border-ring hover:bg-muted/40",
                    )}
                  >
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="truncate font-medium">{row.name}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">{row.price_band ?? ""}</span>
                    </span>
                    <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                      {row.sku} · {row.geometry.width_cm} × {row.geometry.depth_cm} × {row.geometry.height_cm} cm
                    </span>
                  </button>
                </li>
              ))}
              {shown.length === 0 && <li className="text-sm text-muted-foreground">Nothing here yet.</li>}
            </ul>
          </CardContent>
        </Card>

        <Card className="shadow-lg shadow-black/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Ruler className="size-4 text-primary" /> The room
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              {(
                [
                  ["Width", width, setWidth],
                  ["Depth", depth, setDepth],
                  ["Height", height, setHeight],
                ] as const
              ).map(([labelText, value, setter]) => (
                <div key={labelText} className="space-y-2">
                  <Label htmlFor={`ws-${labelText.toLowerCase()}`} className="text-muted-foreground">
                    {labelText} (m)
                  </Label>
                  <Input id={`ws-${labelText.toLowerCase()}`} inputMode="decimal" value={value} onChange={(event) => setter(event.target.value)} disabled={busy} />
                </div>
              ))}
            </div>

            <Button size="lg" className="w-full" onClick={run} disabled={busy || !picked}>
              {busy ? <Loader2 className="animate-spin" /> : <Box className="size-4" />}
              {busy ? "Standing it in the room…" : "Place it in 3D"}
            </Button>

            {error && (
              <p className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                {error}
              </p>
            )}
            {stage >= 0 && !simulation?.scene && (
              <p className="text-xs text-muted-foreground">{STAGES[Math.min(stage, STAGES.length - 1)].label}…</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="shadow-lg shadow-black/5">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <CardTitle>{simulation?.scene ? simulation.scene.product_name : "The room"}</CardTitle>
              <CardDescription className="mt-1">
                {simulation?.scene
                  ? `${width} × ${depth} m, drawn from the geometry worker's own placements.`
                  : "Drag to orbit, scroll to zoom. The scene appears once the pipeline has measured it."}
              </CardDescription>
            </div>
            {simulation?.has_model && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => window.open(`/api/v1/simulations/${simulation.id}/model`, "_blank")}
              >
                <Download className="size-3.5" /> glTF
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-5">
          <SceneViewer spec={simulation?.scene ?? null} />

          {simulation?.fit_report && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">{simulation.room_width_m} × {simulation.room_depth_m} m</Badge>
                <span>{simulation.fit_report.room_area_m2.toFixed(1)} m² room</span>
                <span>{simulation.fit_report.usable_area_m2.toFixed(1)} m² usable</span>
                {simulation.product_profile && <ProductSourceBadge profile={simulation.product_profile} />}
                {simulation.product_profile && <DimensionEstimateWarning profile={simulation.product_profile} compact />}
              </div>
              <div className="rounded-lg border bg-muted/30 p-3">
                <RoomPlan
                  widthM={simulation.room_width_m}
                  depthM={simulation.room_depth_m}
                  report={simulation.fit_report}
                  obstacles={simulation.room_scan?.obstacles ?? simulation.fit_report.obstacles}
                />
              </div>
              <div className="rounded-lg border p-3">
                <DeliveryPath report={simulation.fit_report} />
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
