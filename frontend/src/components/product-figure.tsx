"use client"

import { cn } from "@/lib/utils"

/** Drawing units per metre. The figures are small, so the room is padded rather than cropped. */
const U = 24
const PAD = 0.35 * U

const TONE = {
  unmeasured: "fill-room-product/35 stroke-room-product",
  pass: "fill-success/30 stroke-success",
  fail: "fill-destructive/35 stroke-destructive",
} as const

export type FigureTone = keyof typeof TONE

type Props = {
  widthCm: number
  depthCm: number
  clearanceCm: number
  roomWidthM: number
  roomDepthM: number
  /** Which way the geometry engine settled it, or "unmeasured" before anyone asked. */
  tone: FigureTone
  name: string
  className?: string
}

/** The shop's product image: the piece drawn to scale on the shopper's own floor, from the
 *  centimetres the catalog states. It cannot flatter the box, and it is the same footprint the
 *  geometry engine moves around the room, so the picture and the verdict can't disagree. */
export function ProductFigure({ widthCm, depthCm, clearanceCm, roomWidthM, roomDepthM, tone, name, className }: Props) {
  const roomW = roomWidthM * U
  const roomD = roomDepthM * U
  const itemW = Math.min((widthCm / 100) * U, roomW)
  const itemD = Math.min((depthCm / 100) * U, roomD)
  const clearance = (clearanceCm / 100) * U
  // Against the back wall, off to one side, so the bare floor in front of it reads as the
  // walkway the verdict is about.
  const x = PAD + 2
  const y = PAD + 2

  return (
    <svg
      viewBox={`0 0 ${(roomW + PAD * 2).toFixed(1)} ${(roomD + PAD * 2).toFixed(1)}`}
      className={cn("h-auto w-full", className)}
      role="img"
      aria-label={`${name} footprint in a ${roomWidthM} by ${roomDepthM} metre room`}
    >
      <rect x={PAD} y={PAD} width={roomW} height={roomD} rx="3" className="fill-room-floor/25 stroke-muted-foreground/35" strokeWidth="0.8" />
      {/* One-metre grid: the floor is the scale, so the picture can be read without a caption. */}
      {Array.from({ length: Math.floor(roomWidthM) }, (_, metre) => (
        <line key={`w${metre}`} x1={PAD + (metre + 1) * U} y1={PAD} x2={PAD + (metre + 1) * U} y2={PAD + roomD} className="stroke-muted-foreground/15" strokeWidth="0.6" />
      ))}
      {Array.from({ length: Math.floor(roomDepthM) }, (_, metre) => (
        <line key={`d${metre}`} x1={PAD} y1={PAD + (metre + 1) * U} x2={PAD + roomW} y2={PAD + (metre + 1) * U} className="stroke-muted-foreground/15" strokeWidth="0.6" />
      ))}
      {clearance >= 1.5 && (
        <rect
          x={(x - clearance).toFixed(1)}
          y={(y - clearance).toFixed(1)}
          width={(itemW + clearance * 2).toFixed(1)}
          height={(itemD + clearance * 2).toFixed(1)}
          rx="3"
          className="fill-none stroke-muted-foreground/45"
          strokeWidth="0.7"
          strokeDasharray="2.5 2.5"
        />
      )}
      <rect x={x} y={y} width={itemW.toFixed(1)} height={itemD.toFixed(1)} rx="2" className={TONE[tone]} strokeWidth="1.2" />
    </svg>
  )
}
