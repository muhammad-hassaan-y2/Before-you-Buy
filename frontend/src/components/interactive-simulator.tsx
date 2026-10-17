"use client"

import {
  Activity,
  Box,
  CheckCircle2,
  Compass,
  Cpu,
  Eye,
  Layers,
  Maximize2,
  Move,
  RotateCw,
  Ruler,
  Scan,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react"
import { useId, useMemo, useState } from "react"

import { SceneViewer } from "@/components/scene-viewer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ProductPart, ScenePlacement, SceneSpec } from "@/lib/api"
import { getProductImage } from "@/lib/product-images"
import { cn } from "@/lib/utils"

const DOOR_SWING_M = 0.85
const PADDING_M = 0.5

export type DemoPiece = {
  id: string
  name: string
  category: string
  brand: string
  sku: string
  widthCm: number
  depthCm: number
  heightCm: number
  clearanceCm: number
  material: string
  priceEur: number
  parts: ProductPart[]
}

export const DEMO_PIECES: DemoPiece[] = [
  {
    id: "sofa-kivik",
    name: "Kivik 3-seat sofa",
    category: "sofa",
    brand: "Kivik",
    sku: "SOFA-301",
    widthCm: 220,
    depthCm: 89,
    heightCm: 83,
    clearanceCm: 15,
    material: "fabric",
    priceEur: 799,
    parts: [
      { label: "seat cushion", size_cm: [190, 75, 42], offset_cm: [0, 5, 22], tone: "upholstery" },
      { label: "backrest", size_cm: [220, 20, 83], offset_cm: [0, -35, 42], tone: "upholstery" },
      { label: "left arm", size_cm: [20, 89, 58], offset_cm: [-100, 0, 29], tone: "upholstery" },
      { label: "right arm", size_cm: [20, 89, 58], offset_cm: [100, 0, 29], tone: "upholstery" },
    ],
  },
  {
    id: "table-ekenset",
    name: "Ekenset dining table",
    category: "table",
    brand: "Ekenset",
    sku: "TAB-101",
    widthCm: 150,
    depthCm: 85,
    heightCm: 75,
    clearanceCm: 70,
    material: "solid oak",
    priceEur: 489,
    parts: [
      { label: "table top", size_cm: [150, 85, 4], offset_cm: [0, 0, 73], tone: "timber" },
      { label: "leg FL", size_cm: [6, 6, 71], offset_cm: [-68, 36, 35], tone: "leg" },
      { label: "leg FR", size_cm: [6, 6, 71], offset_cm: [68, 36, 35], tone: "leg" },
      { label: "leg BL", size_cm: [6, 6, 71], offset_cm: [-68, -36, 35], tone: "leg" },
      { label: "leg BR", size_cm: [6, 6, 71], offset_cm: [68, -36, 35], tone: "leg" },
    ],
  },
  {
    id: "desk-uppspeel",
    name: "Uppspeel standing desk",
    category: "desk",
    brand: "Uppspeel",
    sku: "DESK-102",
    widthCm: 160,
    depthCm: 80,
    heightCm: 110,
    clearanceCm: 60,
    material: "black laminate",
    priceEur: 599,
    parts: [
      { label: "desktop", size_cm: [160, 80, 3], offset_cm: [0, 0, 108], tone: "timber" },
      { label: "motor column L", size_cm: [10, 60, 106], offset_cm: [-65, 0, 53], tone: "metal" },
      { label: "motor column R", size_cm: [10, 60, 106], offset_cm: [65, 0, 53], tone: "metal" },
    ],
  },
  {
    id: "bed-malm",
    name: "Malm platform bed",
    category: "bed",
    brand: "Malm",
    sku: "BED-101",
    widthCm: 160,
    depthCm: 206,
    heightCm: 100,
    clearanceCm: 60,
    material: "white oak",
    priceEur: 429,
    parts: [
      { label: "mattress base", size_cm: [160, 200, 35], offset_cm: [0, 0, 17], tone: "linen" },
      { label: "headboard", size_cm: [160, 6, 100], offset_cm: [0, -100, 50], tone: "timber" },
    ],
  },
  {
    id: "chair-poang",
    name: "Poang lounge chair",
    category: "armchair",
    brand: "Poang",
    sku: "CHR-101",
    widthCm: 72,
    depthCm: 77,
    heightCm: 78,
    clearanceCm: 20,
    material: "bentwood birch",
    priceEur: 169,
    parts: [
      { label: "seat & back", size_cm: [60, 70, 70], offset_cm: [0, 0, 35], tone: "linen" },
      { label: "cantilever frame", size_cm: [72, 77, 75], offset_cm: [0, 0, 37], tone: "timber" },
    ],
  },
]

export const ROOM_PRESETS = [
  { label: "Cozy Studio", width: 3.8, depth: 3.2, height: 2.4 },
  { label: "Standard Living Room", width: 4.5, depth: 3.8, height: 2.6 },
  { label: "Spacious Lounge", width: 5.5, depth: 4.2, height: 2.7 },
  { label: "Compact Bedroom", width: 3.4, depth: 3.0, height: 2.4 },
]

export function InteractiveSimulatorEngine({ className }: { className?: string }) {
  const patternId = useId()
  const [mode, setMode] = useState<"2d" | "3d">("2d")
  const [selectedPiece, setSelectedPiece] = useState<DemoPiece>(DEMO_PIECES[0])
  const [roomWidth, setRoomWidth] = useState(4.5)
  const [roomDepth, setRoomDepth] = useState(3.8)
  const [roomHeight, setRoomHeight] = useState(2.5)

  // Relative normalized placement position [0..1]
  const [relX, setRelX] = useState(0.5)
  const [relY, setRelY] = useState(0.65)
  const [rotationDeg, setRotationDeg] = useState(0)
  const [activePipelineStep, setActivePipelineStep] = useState<number>(0)

  // Physical piece dimensions in metres based on current rotation
  const isRotated90 = rotationDeg === 90 || rotationDeg === 270
  const pieceWidthM = (isRotated90 ? selectedPiece.depthCm : selectedPiece.widthCm) / 100
  const pieceDepthM = (isRotated90 ? selectedPiece.widthCm : selectedPiece.depthCm) / 100
  const clearanceM = selectedPiece.clearanceCm / 100

  // Exact centre coordinate in metres (origin is bottom-left corner at door hinge)
  const minX = pieceWidthM / 2 + 0.1
  const maxX = roomWidth - pieceWidthM / 2 - 0.1
  const minY = pieceDepthM / 2 + 0.1
  const maxY = roomDepth - pieceDepthM / 2 - 0.1

  const posX = Math.min(maxX, Math.max(minX, relX * roomWidth))
  const posY = Math.min(maxY, Math.max(minY, relY * roomDepth))

  // Calculate 4-way walkway gaps in metres
  const walkwayLeft = posX - pieceWidthM / 2
  const walkwayRight = roomWidth - (posX + pieceWidthM / 2)
  const walkwayFront = posY - pieceDepthM / 2
  const walkwayBack = roomDepth - (posY + pieceDepthM / 2)
  const tightestWalkway = Math.min(walkwayLeft, walkwayRight, walkwayFront, walkwayBack)

  // Door swing intersection test (door swing quarter circle at x=0, y=0 with radius DOOR_SWING_M)
  // Check if piece bounding box enters the door swing sector
  const pieceLeft = posX - pieceWidthM / 2
  const pieceBottom = posY - pieceDepthM / 2
  const distToDoor = Math.sqrt(pieceLeft * pieceLeft + pieceBottom * pieceBottom)
  const doorBlocked = distToDoor < DOOR_SWING_M + 0.05

  // Spatial clearance verdict
  let verdict: "fits" | "tight" | "blocked" = "fits"
  let verdictMessage = "Fits smoothly with generous walkway clearances all around"
  if (doorBlocked) {
    verdict = "blocked"
    verdictMessage = `Blocks entrance: sweeps into the ${DOOR_SWING_M.toFixed(2)}m doorway swing radius`
  } else if (tightestWalkway < 0.35) {
    verdict = "blocked"
    verdictMessage = `Walkway pinched to ${(tightestWalkway * 100).toFixed(0)}cm — below safe minimum (40cm)`
  } else if (tightestWalkway < 0.6) {
    verdict = "tight"
    verdictMessage = `Walkway is ${(tightestWalkway * 100).toFixed(0)}cm — tight fit, passable but narrow`
  }

  // Construct synthetic real-time SceneSpec for the 3D WebGL engine
  const sceneSpec: SceneSpec = useMemo(() => {
    const coverage = (pieceWidthM * pieceDepthM) / (roomWidth * roomDepth) * 100
    const placements: ScenePlacement[] = [
      {
        label: "Active placement",
        fits: verdict !== "blocked",
        position_m: [posX, 0, posY],
        rotation_deg: rotationDeg,
        walkway_m: {
          left: Number(walkwayLeft.toFixed(2)),
          right: Number(walkwayRight.toFixed(2)),
          front: Number(walkwayFront.toFixed(2)),
          back: Number(walkwayBack.toFixed(2)),
        },
      },
    ]

    return {
      version: "1.0",
      room_width_m: roomWidth,
      room_depth_m: roomDepth,
      room_height_m: roomHeight,
      walls: [],
      door_swing_m: DOOR_SWING_M,
      product_name: selectedPiece.name,
      product_category: selectedPiece.category,
      parts: selectedPiece.parts,
      geometry: {
        width_cm: selectedPiece.widthCm,
        depth_cm: selectedPiece.depthCm,
        height_cm: selectedPiece.heightCm,
        clearance_cm: selectedPiece.clearanceCm,
      },
      clearance_m: clearanceM,
      placements,
      cameras: [
        {
          label: "Isometric",
          position_m: [roomWidth * 1.3, roomHeight * 1.5, roomDepth * 1.3],
          target_m: [roomWidth / 2, 0.4, roomDepth / 2],
          fov_deg: 45,
        },
        {
          label: "Top down",
          position_m: [roomWidth / 2, Math.max(roomWidth, roomDepth) * 1.6, roomDepth / 2],
          target_m: [roomWidth / 2, 0, roomDepth / 2],
          fov_deg: 40,
        },
        {
          label: "Walkway",
          position_m: [0.3, 1.4, 0.3],
          target_m: [posX, 0.5, posY],
          fov_deg: 60,
        },
      ],
      verdict: verdict === "blocked" ? "blocked" : verdict === "tight" ? "tight" : "fits",
      coverage_pct: Number(coverage.toFixed(1)),
    }
  }, [
    roomWidth,
    roomDepth,
    roomHeight,
    selectedPiece,
    posX,
    posY,
    rotationDeg,
    verdict,
    walkwayLeft,
    walkwayRight,
    walkwayFront,
    walkwayBack,
    pieceWidthM,
    pieceDepthM,
    clearanceM,
  ])

  // SVG coordinate transformation for 2D CAD blueprint
  // In SVG: y grows downwards, whereas in room coords: y grows away from front door
  const viewBoxW = roomWidth + PADDING_M * 2
  const viewBoxH = roomDepth + PADDING_M * 2
  const toSvgY = (roomY: number) => roomDepth - roomY

  const productImage = getProductImage(selectedPiece.sku, selectedPiece.category)

  return (
    <div
      className={cn(
        "relative isolate overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-white/[0.04] to-black/80 p-6 shadow-2xl backdrop-blur-2xl lg:p-8",
        className,
      )}
    >
      {/* Background ambient lighting */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 -z-10 h-96 w-[36rem] -translate-x-1/2 rounded-full bg-primary/15 blur-3xl"
      />

      {/* Header bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-[11px] font-semibold text-primary uppercase tracking-wider">
              <Zap className="size-3" /> Spatial AI Engine
            </span>
            <span className="text-xs text-muted-foreground">Interactive 2D & 3D Spatial Simulator</span>
          </div>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white lg:text-3xl">
            See how it fits before you spend a cent.
          </h2>
          <p className="mt-1 text-sm text-zinc-400 max-w-xl">
            Test real pieces in real dimensions. The geometry engine computes millimeter clearances, doorway swings,
            and walkways live.
          </p>
        </div>

        {/* 2D / 3D Mode Toggle Capsule */}
        <div className="flex items-center self-start rounded-full border border-white/15 bg-black/60 p-1 shadow-inner">
          <button
            type="button"
            onClick={() => setMode("2d")}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium transition-all",
              mode === "2d" ? "bg-white text-black shadow-md" : "text-zinc-400 hover:text-white",
            )}
          >
            <Compass className="size-3.5" /> 2D Blueprint
          </button>
          <button
            type="button"
            onClick={() => setMode("3d")}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium transition-all",
              mode === "3d" ? "bg-white text-black shadow-md" : "text-zinc-400 hover:text-white",
            )}
          >
            <Box className="size-3.5" /> 3D Spatial
          </button>
        </div>
      </div>

      {/* Main Grid: Controls & Viewport */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
        {/* Left Column: Visual Viewport (2D CAD or 3D WebGL) */}
        <div className="flex flex-col space-y-4">
          <div className="relative min-h-[380px] w-full overflow-hidden rounded-2xl border border-white/10 bg-[#09090b] shadow-2xl">
            {/* Verdict HUD badge */}
            <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold backdrop-blur-md transition-colors",
                  verdict === "fits"
                    ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-400"
                    : verdict === "tight"
                      ? "border-amber-500/40 bg-amber-500/15 text-amber-300"
                      : "border-rose-500/40 bg-rose-500/15 text-rose-300",
                )}
              >
                <span
                  className={cn(
                    "size-2 rounded-full",
                    verdict === "fits" ? "bg-emerald-400 animate-pulse" : verdict === "tight" ? "bg-amber-400" : "bg-rose-400",
                  )}
                />
                {verdict === "fits" ? "Fits With Room" : verdict === "tight" ? "Tight Fit" : "Clearance Blocked"}
              </span>

              <Badge variant="outline" className="border-white/15 bg-black/50 text-[11px] text-zinc-300 backdrop-blur-md">
                Walkway: {(tightestWalkway * 100).toFixed(0)} cm
              </Badge>
            </div>

            {/* Top Right: Camera Presets or View Hints */}
            <div className="absolute top-4 right-4 z-20 hidden sm:flex items-center gap-1.5">
              <span className="rounded-full border border-white/10 bg-black/60 px-2.5 py-1 text-[10px] text-zinc-400 backdrop-blur-md">
                {mode === "2d" ? "Click anywhere inside to reposition" : "Drag to orbit · Scroll to zoom"}
              </span>
            </div>

            {/* Mode 2D: Architectural Blueprint */}
            {mode === "2d" ? (
              <div
                className="relative flex h-[380px] w-full items-center justify-center p-4 select-none cursor-crosshair lg:h-[430px]"
                onClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect()
                  const normX = (e.clientX - rect.left) / rect.width
                  const normY = 1 - (e.clientY - rect.top) / rect.height
                  setRelX(Math.max(0.15, Math.min(0.85, normX)))
                  setRelY(Math.max(0.15, Math.min(0.85, normY)))
                }}
              >
                <svg
                  viewBox={`${-PADDING_M} ${-PADDING_M} ${viewBoxW} ${viewBoxH}`}
                  className="h-full w-auto max-w-full drop-shadow-2xl"
                  role="img"
                  aria-label="2D Architectural Blueprint"
                >
                  <defs>
                    <pattern id={patternId} width="0.5" height="0.5" patternUnits="userSpaceOnUse">
                      <path d="M0.5 0H0V0.5" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="0.015" />
                    </pattern>
                  </defs>

                  {/* Room Floor with Grid */}
                  <rect x={-PADDING_M} y={-PADDING_M} width={viewBoxW} height={viewBoxH} fill="none" />
                  <rect width={roomWidth} height={roomDepth} y={toSvgY(roomDepth)} fill="#121215" rx={0.06} />
                  <rect width={roomWidth} height={roomDepth} y={toSvgY(roomDepth)} fill={`url(#${patternId})`} />

                  {/* Room Perimeter Walls */}
                  <rect
                    width={roomWidth}
                    height={roomDepth}
                    y={toSvgY(roomDepth)}
                    fill="none"
                    stroke="#3f3f46"
                    strokeWidth={0.07}
                    rx={0.06}
                  />

                  {/* Door Swing Quarter-Circle Arc (hinge at bottom-left corner 0,0) */}
                  <path
                    d={`M ${DOOR_SWING_M} ${toSvgY(0)} A ${DOOR_SWING_M} ${DOOR_SWING_M} 0 0 0 0 ${toSvgY(DOOR_SWING_M)} L 0 ${toSvgY(0)} Z`}
                    fill={doorBlocked ? "rgba(244,63,94,0.18)" : "rgba(255,255,255,0.05)"}
                    stroke={doorBlocked ? "#f43f5e" : "#71717a"}
                    strokeWidth={0.025}
                    strokeDasharray="0.06 0.04"
                  />
                  <line x1={0} y1={toSvgY(0)} x2={0} y2={toSvgY(DOOR_SWING_M)} stroke="#a1a1aa" strokeWidth={0.04} />
                  <text x={0.12} y={toSvgY(0.25)} fill="#71717a" fontSize={0.18} fontFamily="monospace">
                    Entrance Door (0.85m)
                  </text>

                  {/* Walkway Clearance Vectors to Walls */}
                  <line
                    x1={posX - pieceWidthM / 2}
                    y1={toSvgY(posY)}
                    x2={0}
                    y2={toSvgY(posY)}
                    stroke="rgba(255,255,255,0.3)"
                    strokeWidth={0.02}
                    strokeDasharray="0.05 0.04"
                  />
                  <line
                    x1={posX + pieceWidthM / 2}
                    y1={toSvgY(posY)}
                    x2={roomWidth}
                    y2={toSvgY(posY)}
                    stroke="rgba(255,255,255,0.3)"
                    strokeWidth={0.02}
                    strokeDasharray="0.05 0.04"
                  />
                  <line
                    x1={posX}
                    y1={toSvgY(posY - pieceDepthM / 2)}
                    x2={posX}
                    y2={toSvgY(0)}
                    stroke="rgba(255,255,255,0.3)"
                    strokeWidth={0.02}
                    strokeDasharray="0.05 0.04"
                  />
                  <line
                    x1={posX}
                    y1={toSvgY(posY + pieceDepthM / 2)}
                    x2={posX}
                    y2={toSvgY(roomDepth)}
                    stroke="rgba(255,255,255,0.3)"
                    strokeWidth={0.02}
                    strokeDasharray="0.05 0.04"
                  />

                  {/* Walkway Dimension Text Callouts */}
                  <text x={walkwayLeft / 2} y={toSvgY(posY) - 0.08} fill="#a1a1aa" fontSize={0.16} textAnchor="middle">
                    {walkwayLeft.toFixed(2)}m
                  </text>
                  <text
                    x={posX + pieceWidthM / 2 + walkwayRight / 2}
                    y={toSvgY(posY) - 0.08}
                    fill="#a1a1aa"
                    fontSize={0.16}
                    textAnchor="middle"
                  >
                    {walkwayRight.toFixed(2)}m
                  </text>
                  <text x={posX + 0.12} y={toSvgY(walkwayFront / 2)} fill="#a1a1aa" fontSize={0.16}>
                    {walkwayFront.toFixed(2)}m
                  </text>
                  <text
                    x={posX + 0.12}
                    y={toSvgY(posY + pieceDepthM / 2 + walkwayBack / 2)}
                    fill="#a1a1aa"
                    fontSize={0.16}
                  >
                    {walkwayBack.toFixed(2)}m
                  </text>

                  {/* Outer Clearance Envelope Buffer */}
                  <rect
                    x={posX - pieceWidthM / 2 - clearanceM}
                    y={toSvgY(posY + pieceDepthM / 2 + clearanceM)}
                    width={pieceWidthM + clearanceM * 2}
                    height={pieceDepthM + clearanceM * 2}
                    fill="none"
                    stroke={verdict === "fits" ? "#10b981" : verdict === "tight" ? "#f59e0b" : "#f43f5e"}
                    strokeOpacity={0.4}
                    strokeWidth={0.02}
                    strokeDasharray="0.06 0.04"
                    rx={0.05}
                  />

                  {/* Furniture Piece Footprint */}
                  <rect
                    x={posX - pieceWidthM / 2}
                    y={toSvgY(posY + pieceDepthM / 2)}
                    width={pieceWidthM}
                    height={pieceDepthM}
                    fill={verdict === "fits" ? "#10b981" : verdict === "tight" ? "#f59e0b" : "#f43f5e"}
                    fillOpacity={0.25}
                    stroke={verdict === "fits" ? "#10b981" : verdict === "tight" ? "#f59e0b" : "#f43f5e"}
                    strokeWidth={0.04}
                    rx={0.05}
                  />

                  {/* Center Dot & Label */}
                  <circle cx={posX} cy={toSvgY(posY)} r={0.06} fill="#ffffff" />
                  <text
                    x={posX}
                    y={toSvgY(posY) + 0.06}
                    fill="#ffffff"
                    fontSize={0.2}
                    fontWeight="bold"
                    textAnchor="middle"
                  >
                    {selectedPiece.name}
                  </text>
                  <text
                    x={posX}
                    y={toSvgY(posY) + 0.28}
                    fill="#d4d4d8"
                    fontSize={0.14}
                    textAnchor="middle"
                  >
                    {(selectedPiece.widthCm / 100).toFixed(2)}m × {(selectedPiece.depthCm / 100).toFixed(2)}m
                  </text>
                </svg>
              </div>
            ) : (
              /* Mode 3D: WebGL Spatial Viewport */
              <div className="relative h-[380px] w-full lg:h-[430px]">
                <SceneViewer spec={sceneSpec} className="h-full w-full border-none" />
              </div>
            )}
          </div>

          {/* Interactive Quick Placements & Rotate Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-black/40 p-3 text-xs">
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Move className="size-3.5 text-primary" /> Placement:
              <button
                type="button"
                onClick={() => {
                  setRelX(0.5)
                  setRelY(0.7)
                }}
                className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-zinc-300 hover:bg-white/10"
              >
                Back Wall
              </button>
              <button
                type="button"
                onClick={() => {
                  setRelX(0.5)
                  setRelY(0.5)
                }}
                className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-zinc-300 hover:bg-white/10"
              >
                Centered
              </button>
              <button
                type="button"
                onClick={() => {
                  setRelX(0.25)
                  setRelY(0.7)
                }}
                className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-zinc-300 hover:bg-white/10"
              >
                Left Corner
              </button>
              <button
                type="button"
                onClick={() => {
                  setRelX(0.75)
                  setRelY(0.7)
                }}
                className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-zinc-300 hover:bg-white/10"
              >
                Right Corner
              </button>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRotationDeg((r) => (r + 90) % 360)}
              className="gap-1.5 rounded-full border-white/15 bg-white/5 text-xs text-white hover:bg-white/10"
            >
              <RotateCw className="size-3.5" /> Rotate ({rotationDeg}°)
            </Button>
          </div>
        </div>

        {/* Right Column: Piece Selector, Room Specs & AI Pipeline */}
        <div className="flex flex-col space-y-5">
          {/* Active Piece Studio Preview Card */}
          <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/60 p-4 transition-all">
            <div className="flex items-center gap-4">
              <div className="relative size-20 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-black">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={productImage.url}
                  alt={productImage.alt}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="bg-white/10 text-[10px] text-zinc-300">
                    {selectedPiece.category}
                  </Badge>
                  <span className="font-mono text-xs text-zinc-400">{selectedPiece.sku}</span>
                </div>
                <h3 className="mt-1 font-semibold text-base text-white truncate">{selectedPiece.name}</h3>
                <p className="mt-0.5 font-mono text-xs text-zinc-400">
                  {selectedPiece.widthCm} × {selectedPiece.depthCm} × {selectedPiece.heightCm} cm · {selectedPiece.material}
                </p>
                <p className="mt-1 font-semibold text-primary">€{selectedPiece.priceEur}</p>
              </div>
            </div>

            {/* Quick Catalog Switcher */}
            <div className="mt-3.5 border-t border-white/10 pt-3">
              <p className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-2">
                Choose a piece to test in real scale:
              </p>
              <div className="flex flex-wrap gap-1.5">
                {DEMO_PIECES.map((piece) => (
                  <button
                    key={piece.id}
                    type="button"
                    onClick={() => {
                      setSelectedPiece(piece)
                      setRotationDeg(0)
                    }}
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs font-medium transition-all",
                      selectedPiece.id === piece.id
                        ? "border-primary bg-primary text-black font-semibold shadow-sm"
                        : "border-white/10 bg-white/5 text-zinc-300 hover:border-white/25 hover:text-white",
                    )}
                  >
                    {piece.name.split(" ")[0]} ({piece.category})
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Room Presets & Sliders */}
          <div className="rounded-2xl border border-white/10 bg-zinc-900/60 p-4">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-medium text-zinc-300">
                <Ruler className="size-3.5 text-primary" /> Target Room Dimensions
              </span>
              <span className="font-mono text-xs text-primary font-semibold">
                {roomWidth} × {roomDepth} m ({(roomWidth * roomDepth).toFixed(1)} m²)
              </span>
            </div>

            {/* Room Size Presets */}
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {ROOM_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    setRoomWidth(preset.width)
                    setRoomDepth(preset.depth)
                    setRoomHeight(preset.height)
                  }}
                  className={cn(
                    "rounded-lg border px-2.5 py-1 text-[11px] transition-colors",
                    roomWidth === preset.width && roomDepth === preset.depth
                      ? "border-white/40 bg-white/15 text-white font-medium"
                      : "border-white/10 bg-white/5 text-zinc-400 hover:text-zinc-200",
                  )}
                >
                  {preset.label} ({preset.width}×{preset.depth}m)
                </button>
              ))}
            </div>

            {/* Verdict Explanation Message */}
            <div className="mt-4 rounded-xl border border-white/10 bg-black/40 p-3 text-xs">
              <div className="flex items-center gap-2">
                <ShieldCheck className={cn("size-4 shrink-0", verdict === "fits" ? "text-emerald-400" : verdict === "tight" ? "text-amber-400" : "text-rose-400")} />
                <span className="font-medium text-zinc-200">{verdictMessage}</span>
              </div>
            </div>
          </div>

          {/* "How It Works" 4-Step Interactive Pipeline Tour */}
          <div className="rounded-2xl border border-white/10 bg-zinc-900/60 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="flex items-center gap-1.5 text-xs font-medium text-zinc-300">
                <Cpu className="size-3.5 text-primary" /> How The AI Spatial Engine Works
              </span>
              <span className="text-[10px] text-zinc-500">4-Step Verification</span>
            </div>

            <div className="space-y-2">
              {[
                {
                  step: 1,
                  title: "1. Computer Vision Room Scan",
                  desc: "OpenCV measures room perimeter, door jambs, swing arc, and fixed obstacles directly from photos.",
                },
                {
                  step: 2,
                  title: "2. vLLM Multi-Modal Reading",
                  desc: "AMD ROCm-hosted model extracts true 3D bounding box (cm), assembly margins, and cartons from listing URLs.",
                },
                {
                  step: 3,
                  title: "3. Shapely Polygon Clearance",
                  desc: "Computes Minkowski sum, buffer zones, and door swing intersections without guessing.",
                },
                {
                  step: 4,
                  title: "4. Real-Time 3D Spatial Assembly",
                  desc: "Generates glTF SceneSpec coordinates for zero-latency 2D blueprint & 3D browser simulation.",
                },
              ].map((item, idx) => (
                <button
                  key={item.step}
                  type="button"
                  onClick={() => setActivePipelineStep(idx)}
                  className={cn(
                    "w-full text-left rounded-xl p-2.5 transition-all border",
                    activePipelineStep === idx
                      ? "border-primary/50 bg-primary/10 text-white"
                      : "border-transparent bg-white/[0.02] text-zinc-400 hover:bg-white/[0.05]",
                  )}
                >
                  <p className="font-semibold text-xs text-zinc-200">{item.title}</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-zinc-400">{item.desc}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
