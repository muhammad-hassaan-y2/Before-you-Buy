"use client"

import { AlertTriangle, CheckCircle2, OctagonX, type LucideIcon } from "lucide-react"

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

const VERDICT_TONE: Record<string, { box: string; icon: string; Icon: LucideIcon }> = {
  success: { box: "border-success/40 bg-success/10", icon: "text-success", Icon: CheckCircle2 },
  warning: { box: "border-warning/50 bg-warning/10", icon: "text-warning", Icon: AlertTriangle },
  destructive: { box: "border-destructive/40 bg-destructive/10", icon: "text-destructive", Icon: OctagonX },
}

/** The answer the page exists for, so it is the largest thing in the result — not a chip. */
export function VerdictBanner({ verdict, tightest }: { verdict: string; tightest: number | null }) {
  const entry = VERDICT[verdict]
  const tone = VERDICT_TONE[entry?.variant ?? "destructive"]
  return (
    <div role="status" data-verdict={verdict} className={cn("flex items-center gap-4 rounded-lg border-2 px-5 py-4", tone.box)}>
      <tone.Icon className={cn("size-9 shrink-0", tone.icon)} aria-hidden />
      <div className="min-w-0">
        <p className="eyebrow text-muted-foreground">Verdict</p>
        <p className="display text-2xl text-balance sm:text-3xl">{entry?.label ?? verdict}</p>
        {tightest !== null && <p className="num mt-0.5 text-sm text-muted-foreground">Tightest gap {tightest.toFixed(2)} m</p>}
      </div>
    </div>
  )
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
  // The number the verdict turns on: the narrowest gap left around the piece that is being looked at.
  const shown = active ?? report.placements.find((spot) => spot.fits) ?? report.placements[0] ?? null
  const walkways = Object.values(shown?.walkway_m ?? {}).filter((gap) => typeof gap === "number")
  const tightest = walkways.length ? Math.min(...walkways) : null

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        <VerdictBanner verdict={report.verdict} tightest={tightest} />
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            {profile
              ? `${profile.geometry.width_cm.toFixed(0)} × ${profile.geometry.depth_cm.toFixed(0)} × ${profile.geometry.height_cm.toFixed(0)} cm`
              : `${report.placements.length} placements tested`}
          </Badge>
          {profile && <ProductSourceBadge profile={profile} />}
          {scan && <Badge variant="outline">{ROOM_SCAN_LABEL[scan.method] ?? scan.method}</Badge>}
        </div>
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

      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {[
          ["Room", `${report.room_area_m2.toFixed(1)} m²`, null],
          ["Usable", `${report.usable_area_m2.toFixed(1)} m²`, null],
          ["Occupied", `${report.coverage_pct.toFixed(1)} %`, null],
          ["Tightest gap", tightest === null ? null : `${tightest.toFixed(2)} m`, tightest !== null && tightest < 0.6 ? "text-warning" : null],
        ].map(([labelText, value, tone]) => (
          <div key={labelText as string} className="rounded-md border border-border/60 bg-surface px-3.5 py-3">
            <dt className="eyebrow text-muted-foreground">{labelText}</dt>
            <dd className={cn("num mt-1 text-lg font-semibold", tone ?? undefined)}>{value ?? "—"}</dd>
          </div>
        ))}
      </dl>

      <div className="rounded-md border p-3">
        <DeliveryPath report={report} />
      </div>

      {profile && (
        <div className="rounded-md border p-3 text-sm">
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
