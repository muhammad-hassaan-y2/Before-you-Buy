"use client"

import { Activity, Box, Cpu, Loader2, Ruler, Scan } from "lucide-react"
import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import type { SimulationStage } from "@/lib/api"
import { cn } from "@/lib/utils"

const PADDING_M = 0.4
const DOOR_SWING_M = 0.85

const STAGE_DESCRIPTIONS: Record<string, { label: string; detail: string; service: string }> = {
  pending: {
    label: "Simulation queued",
    detail: "Dispatching request to api-gateway and event bus...",
    service: "api-gateway",
  },
  cataloguing: {
    label: "Matching SKU in catalog",
    detail: "Resolving product identifier and dimensions against catalog index...",
    service: "catalog-service",
  },
  enriching: {
    label: "Reading product listing",
    detail: "Inference worker reading geometry with AMD-hosted vision/LLM...",
    service: "inference-service",
  },
  measuring: {
    label: "Extracting 3D geometry",
    detail: "Computing bounding box, clearance rules, and part definitions...",
    service: "inference-service",
  },
  scanning: {
    label: "Scanning room & obstacles",
    detail: "Analyzing room photo with OpenCV to detect perimeter and fixed obstacles...",
    service: "vision-service",
  },
  fitting: {
    label: "Solving floor plan & walkways",
    detail: "Shapely geometry engine calculating placement polygons and walkway paths...",
    service: "geometry-service",
  },
  rendering: {
    label: "Building 3D scene",
    detail: "Generating SceneSpec and glTF assets for browser viewport...",
    service: "scene-service",
  },
}

type Props = {
  widthM: number
  depthM: number
  heightM?: number
  status?: SimulationStage
  productName?: string
  notes?: string
  photoName?: string
  candidate?: {
    name?: string
    geometry?: {
      width_cm: number
      depth_cm: number
      height_cm: number
    }
  } | null
}

export function SimulatingRoom({
  widthM,
  depthM,
  heightM = 2.4,
  status = "fitting",
  productName,
  notes,
  photoName,
  candidate,
}: Props) {
  const [pulsePos, setPulsePos] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setPulsePos((p) => (p + 1) % 100)
    }, 40)
    return () => clearInterval(timer)
  }, [])

  const viewBoxWidth = widthM + PADDING_M * 2
  const viewBoxHeight = depthM + PADDING_M * 2
  const y = (val: number) => depthM - val

  const stageInfo = STAGE_DESCRIPTIONS[status] ?? {
    label: "Running simulation",
    detail: "Measuring room and testing clearance...",
    service: "pipeline",
  }

  // Calculate approximate placement box in centre if candidate or default exists
  const prodW = (candidate?.geometry?.width_cm ?? 200) / 100
  const prodD = (candidate?.geometry?.depth_cm ?? 90) / 100
  const prodX = Math.max(0.2, (widthM - prodW) / 2)
  const prodY = Math.max(DOOR_SWING_M + 0.2, (depthM - prodD) / 2)

  // Scan beam vertical position (0 to depthM)
  const beamY = (pulsePos / 100) * depthM

  return (
    <div className="space-y-4">
      {/* Live Pipeline HUD banner */}
      <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 transition-all">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="relative flex size-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
              <span className="relative inline-flex size-3 rounded-full bg-primary" />
            </span>
            <span className="font-semibold text-sm tracking-tight">{stageInfo.label}</span>
          </div>
          <Badge variant="outline" className="font-mono text-[11px] text-primary border-primary/30">
            {stageInfo.service}
          </Badge>
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">{stageInfo.detail}</p>
      </div>

      {/* Real-time Room Simulation Blueprint */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-card/60 p-4 shadow-inner">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2">
            <Scan className="size-3.5 text-primary animate-spin" style={{ animationDuration: "6s" }} />
            <span className="font-medium text-foreground">Active Room Simulation</span>
            <span className="text-muted-foreground">·</span>
            <span className="font-mono text-muted-foreground">
              {widthM.toFixed(1)} × {depthM.toFixed(1)} m ({(widthM * depthM).toFixed(1)} m²)
            </span>
          </div>
          {photoName && (
            <Badge variant="secondary" className="text-[10px]">
              photo: {photoName}
            </Badge>
          )}
        </div>

        <div className="dark relative mx-auto w-full max-w-md overflow-hidden rounded-xl border border-border/70 bg-[#0f0d0c]/80 p-2 text-foreground">
          <svg
            viewBox={`${-PADDING_M} ${-PADDING_M} ${viewBoxWidth} ${viewBoxHeight}`}
            className="w-full h-auto drop-shadow-sm select-none"
            role="img"
            aria-label={`Simulating ${widthM} by ${depthM} metre room`}
          >
            <defs>
              <pattern id="sim-grid" width="0.5" height="0.5" patternUnits="userSpaceOnUse">
                <path d="M0.5 0H0V0.5" fill="none" stroke="currentColor" strokeOpacity="0.12" strokeWidth="0.015" />
              </pattern>
              <linearGradient id="scanBeamGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="var(--primary)" stopOpacity="0" />
                <stop offset="85%" stopColor="var(--primary)" stopOpacity="0.15" />
                <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.8" />
              </linearGradient>
            </defs>

            {/* Background & Floor */}
            <rect x={-PADDING_M} y={-PADDING_M} width={viewBoxWidth} height={viewBoxHeight} fill="none" />
            <rect width={widthM} height={depthM} y={y(depthM)} fill="#151311" />
            <rect width={widthM} height={depthM} y={y(depthM)} fill="url(#sim-grid)" className="text-primary" />

            {/* Room Perimeter Walls */}
            <rect
              width={widthM}
              height={depthM}
              y={y(depthM)}
              fill="none"
              stroke="var(--primary)"
              strokeOpacity="0.4"
              strokeWidth={0.05}
              rx={0.04}
            />

            {/* Door Swing Arc */}
            <path
              d={`M ${DOOR_SWING_M} ${y(0)} A ${DOOR_SWING_M} ${DOOR_SWING_M} 0 0 0 0 ${y(DOOR_SWING_M)} L 0 ${y(0)} Z`}
              fill="var(--primary)"
              fillOpacity="0.05"
              stroke="var(--primary)"
              strokeOpacity="0.4"
              strokeWidth={0.02}
              strokeDasharray="0.06 0.04"
            />
            <line x1={0} y1={y(0)} x2={0} y2={y(DOOR_SWING_M)} stroke="var(--primary)" strokeWidth={0.04} />

            {/* Scanning Laser Beam */}
            <rect
              x={0}
              y={y(beamY)}
              width={widthM}
              height={Math.min(0.4, beamY)}
              fill="url(#scanBeamGrad)"
            />
            <line
              x1={0}
              y1={y(beamY)}
              x2={widthM}
              y2={y(beamY)}
              stroke="var(--primary)"
              strokeWidth={0.03}
              strokeOpacity="0.9"
            />

            {/* Simulated Candidate Placement Footprint (pulsing outline) */}
            <rect
              x={prodX}
              y={y(prodY + prodD)}
              width={Math.min(prodW, widthM - prodX - 0.1)}
              height={Math.min(prodD, depthM - prodY - 0.1)}
              fill="var(--primary)"
              fillOpacity="0.12"
              stroke="var(--primary)"
              strokeWidth={0.03}
              strokeDasharray="0.08 0.05"
              rx={0.05}
              className="animate-pulse"
            />

            {/* Center crosshair on piece */}
            <circle
              cx={prodX + prodW / 2}
              cy={y(prodY + prodD / 2)}
              r={0.06}
              fill="var(--primary)"
              fillOpacity="0.8"
            />

            {/* Walkway Clearance Vectors (dashed lines indicating clearance tests) */}
            <line
              x1={prodX}
              y1={y(prodY + prodD / 2)}
              x2={0}
              y2={y(prodY + prodD / 2)}
              stroke="currentColor"
              strokeOpacity="0.25"
              strokeWidth={0.015}
              strokeDasharray="0.04 0.04"
            />
            <line
              x1={prodX + prodW}
              y1={y(prodY + prodD / 2)}
              x2={widthM}
              y2={y(prodY + prodD / 2)}
              stroke="currentColor"
              strokeOpacity="0.25"
              strokeWidth={0.015}
              strokeDasharray="0.04 0.04"
            />
          </svg>
        </div>

        {/* Live Status Indicators */}
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-muted-foreground sm:grid-cols-4">
          <div className="flex items-center gap-1.5 rounded-lg border bg-muted/20 px-2.5 py-1.5">
            <Ruler className="size-3 text-primary shrink-0" />
            <span className="truncate">Width: {widthM}m</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg border bg-muted/20 px-2.5 py-1.5">
            <Ruler className="size-3 text-primary shrink-0" />
            <span className="truncate">Depth: {depthM}m</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg border bg-muted/20 px-2.5 py-1.5">
            <Box className="size-3 text-primary shrink-0" />
            <span className="truncate">Height: {heightM}m</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg border bg-muted/20 px-2.5 py-1.5">
            <Cpu className="size-3 text-primary shrink-0" />
            <span className="truncate">{status}</span>
          </div>
        </div>

        {(productName || notes) && (
          <p className="mt-2 text-center text-xs text-muted-foreground truncate">
            Target piece: <span className="text-foreground font-medium">{productName || notes}</span>
          </p>
        )}
      </div>
    </div>
  )
}
