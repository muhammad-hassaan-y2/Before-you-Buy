"use client"

import { AlertTriangle, CheckCircle2 } from "lucide-react"

import { DeliveryPath } from "@/components/delivery-path"
import { FitViews } from "@/components/fit-views"
import { DimensionEstimateWarning, ProductSourceBadge } from "@/components/product-provenance"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ROOM_SCAN_LABEL, type Simulation, type SimulationStage } from "@/lib/api"
import { cn } from "@/lib/utils"

export const STEPS: { key: SimulationStage; label: string }[] = [
  { key: "pending", label: "Queued" },
  { key: "cataloguing", label: "Matching the SKU" },
  { key: "enriching", label: "Reading the listing" },
  { key: "scanning", label: "Measuring the room" },
  { key: "fitting", label: "Fitting the floor plan" },
  { key: "completed", label: "Ready" },
]

export const VERDICT: Record<string, { label: string; variant: "success" | "warning" | "destructive" }> = {
  fits: { label: "Fits with room to move", variant: "success" },
  tight: { label: "Fits, but tight", variant: "warning" },
  too_large: { label: "Too large for this room", variant: "destructive" },
  blocked: { label: "No clear placement", variant: "destructive" },
}

/** One dot per worker, lit by the status the gateway reported. Nothing here is a decoration:
 *  a dot that is on means that service answered for this simulation. */
export function ProgressStrip({ status, started }: { status?: SimulationStage; started: boolean }) {
  const index = status ? STEPS.findIndex((step) => step.key === status) : started ? 0 : -1
  if (index < 0) return null
  return (
    <ol className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
      {STEPS.map((step, at) => (
        <li key={step.key} className="flex items-center gap-1.5">
          <span
            className={cn(
              "size-1.5 rounded-full transition-colors",
              at < index || status === "completed" ? "bg-success" : at === index ? "bg-primary animate-pulse" : "bg-muted-foreground/30",
            )}
          />
          {at > 0 && <span className="mr-1 h-px w-4 bg-border" />}
          {step.label}
        </li>
      ))}
    </ol>
  )
}

type Props = {
  simulation: Simulation
  /** The label of the placement being looked at, or null for the first one that fits. */
  placement: string | null
  onPlacement: (label: string) => void
}

/** Everything a settled simulation proved, drawn from its own payload: badges from the workers,
 *  the plan and the room from the same scene spec, and the walkways geometry measured. */
export function FitResult({ simulation, placement, onPlacement }: Props) {
  const report = simulation.fit_report
  const profile = simulation.product_profile ?? null
  const scan = simulation.room_scan ?? null
  if (!report) return null

  // Geometry measures the scanned room, which is the shopper's own when the photo could not be read.
  const roomWidth = scan?.width_m ?? simulation.room_width_m
  const roomDepth = scan?.depth_m ?? simulation.room_depth_m
  const active = report.placements.find((spot) => spot.label === placement) ?? null

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={VERDICT[report.verdict]?.variant ?? "secondary"}>{VERDICT[report.verdict]?.label ?? report.verdict}</Badge>
        <Badge variant="outline">
          {profile
            ? `${profile.geometry.width_cm.toFixed(0)} × ${profile.geometry.depth_cm.toFixed(0)} × ${profile.geometry.height_cm.toFixed(0)} cm`
            : `${report.placements.length} placements tested`}
        </Badge>
        {profile && <ProductSourceBadge profile={profile} />}
        {scan && <Badge variant="outline">{ROOM_SCAN_LABEL[scan.method] ?? scan.method}</Badge>}
      </div>

      {profile && <DimensionEstimateWarning profile={profile} />}

      <FitViews
        report={report}
        widthM={roomWidth}
        depthM={roomDepth}
        placement={active}
        obstacles={scan?.obstacles ?? report.obstacles}
        scene={simulation.scene ?? null}
      />

      <dl className="grid grid-cols-3 gap-3 text-sm">
        {[
          ["Room", `${report.room_area_m2.toFixed(1)} m²`],
          ["Usable", `${report.usable_area_m2.toFixed(1)} m²`],
          ["Occupied", `${report.coverage_pct.toFixed(1)} %`],
        ].map(([labelText, value]) => (
          <div key={labelText} className="rounded-xl border p-3">
            <dt className="text-xs text-muted-foreground">{labelText}</dt>
            <dd className="font-mono text-base tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="rounded-xl border p-3">
        <DeliveryPath report={report} />
      </div>

      {profile && (
        <div className="rounded-xl border p-3 text-sm">
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

      {report.placements.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t pt-4">
          {report.placements.map((spot) => (
            <Button
              key={spot.label}
              type="button"
              size="sm"
              variant={active?.label === spot.label ? "default" : "outline"}
              onClick={() => onPlacement(spot.label)}
            >
              {spot.fits ? <CheckCircle2 className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
              {spot.label}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}
