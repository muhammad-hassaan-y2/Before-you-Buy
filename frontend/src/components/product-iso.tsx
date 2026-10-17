/** A piece drawn from the shop's own part boxes, in isometric.
 *
 *  Not a stock photo and not a decoration: every edge here is a centimetre the catalog publishes
 *  and the geometry engine places, split into the same sub-boxes the 3D workspace is built from.
 *  Two pieces of the same category look different because they are different sizes.
 */

import type { ProductPart } from "@/lib/api"
import { cn } from "@/lib/utils"

const COS = Math.cos(Math.PI / 6)
const SIN = 0.5

/** The tone each part carries, tinted by what the piece is upholstered or built in. */
const MATERIAL: Record<string, string> = {
  fabric: "#7A6C5D",
  linen: "#9C8F7A",
  velour: "#6E5057",
  velvet: "#6E5057",
  leather: "#6B483A",
  birch: "#9C7B4E",
  pine: "#A98A5F",
  "oak veneer": "#8A6238",
  oak: "#8A6238",
  walnut: "#5E422C",
  glass: "#71909A",
  steel: "#6F6D6A",
  aluminium: "#82807D",
  polyester: "#7C7367",
  wool: "#8E8271",
  rattan: "#96784A",
  marble: "#ADA59A",
}
const FALLBACK = "#6E6459"

/** The three faces a box shows from this angle, each lit differently. */
const SHADE = { top: 0.22, left: 0.0, right: -0.2 }

type Box = { x0: number; x1: number; y0: number; y1: number; z0: number; z1: number }

function project(x: number, y: number, z: number): [number, number] {
  return [(x - y) * COS, (x + y) * SIN - z]
}

function corners(box: Box): [number, number, number][] {
  return [
    [box.x0, box.y0, box.z0],
    [box.x1, box.y0, box.z0],
    [box.x1, box.y1, box.z0],
    [box.x0, box.y1, box.z0],
    [box.x0, box.y0, box.z1],
    [box.x1, box.y0, box.z1],
    [box.x1, box.y1, box.z1],
    [box.x0, box.y1, box.z1],
  ]
}

/** The part boxes as the camera sees them: sorted far-to-near so a nearer face covers a further one. */
export function isoBoxes(parts: ProductPart[]): { box: Box; depth: number }[] {
  return parts
    .map((part) => {
      const [w, d, h] = part.size_cm
      const [x, y, z] = part.offset_cm
      const box: Box = { x0: x - w / 2, x1: x + w / 2, y0: y - d / 2, y1: y + d / 2, z0: z - h / 2, z1: z + h / 2 }
      return { box, depth: (x + y + z) * 2 }
    })
    .sort((a, b) => a.depth - b.depth)
}

function face(box: Box, which: keyof typeof SHADE): string {
  const points =
    which === "top"
      ? [
          [box.x0, box.y0, box.z1],
          [box.x1, box.y0, box.z1],
          [box.x1, box.y1, box.z1],
          [box.x0, box.y1, box.z1],
        ]
      : which === "right"
        ? [
            [box.x1, box.y0, box.z0],
            [box.x1, box.y1, box.z0],
            [box.x1, box.y1, box.z1],
            [box.x1, box.y0, box.z1],
          ]
        : [
            [box.x0, box.y1, box.z0],
            [box.x1, box.y1, box.z0],
            [box.x1, box.y1, box.z1],
            [box.x0, box.y1, box.z1],
          ]
  return points.map(([x, y, z]) => project(x, y, z).map((value) => value.toFixed(1)).join(",")).join(" ")
}

function mix(hex: string, amount: number): string {
  const value = Number.parseInt(hex.slice(1), 16)
  const target = amount > 0 ? 255 : 0
  const step = Math.abs(amount)
  const channel = (shift: number) => {
    const base = (value >> shift) & 255
    return Math.round(base + (target - base) * step)
      .toString(16)
      .padStart(2, "0")
  }
  return `#${channel(16)}${channel(8)}${channel(0)}`
}

type Props = {
  parts?: ProductPart[]
  widthCm: number
  depthCm: number
  heightCm: number
  clearanceCm?: number
  material?: string | null
  /** The floor the piece asks for, drawn under it: its own footprint plus its clearance. */
  showClearance?: boolean
  name: string
  className?: string
}

export function ProductIso({ parts, widthCm, depthCm, heightCm, clearanceCm = 0, material, showClearance = false, name, className }: Props) {
  const boxes: ProductPart[] = parts?.length
    ? parts
    : [{ label: name, size_cm: [widthCm, depthCm, heightCm], offset_cm: [0, 0, heightCm / 2], tone: "body" }]
  const base = MATERIAL[(material ?? "").toLowerCase()] ?? FALLBACK
  const drawn = isoBoxes(boxes)

  // One frame around the whole piece, so a 60 cm stool and a 286 cm sofa both fill their card.
  const footprint: Box = { x0: -widthCm / 2, x1: widthCm / 2, y0: -depthCm / 2, y1: depthCm / 2, z0: 0, z1: heightCm }
  const ask = clearanceCm > 0 ? clearanceCm : 0
  const room: Box = {
    x0: footprint.x0 - ask,
    x1: footprint.x1 + ask,
    y0: footprint.y0 - ask,
    y1: footprint.y1 + ask,
    z0: 0,
    z1: 0,
  }
  const points = [footprint, room].flatMap((box) => corners(box).map(([x, y, z]) => project(x, y, z)))
  const xs = points.map(([x]) => x)
  const ys = points.map(([, y]) => y)
  const pad = Math.max(widthCm, depthCm) * 0.09
  const view = {
    left: Math.min(...xs) - pad,
    top: Math.min(...ys) - pad,
    width: Math.max(...xs) - Math.min(...xs) + pad * 2,
    height: Math.max(...ys) - Math.min(...ys) + pad * 2,
  }
  const shadow = [
    [room.x0, room.y0, 0],
    [room.x1, room.y0, 0],
    [room.x1, room.y1, 0],
    [room.x0, room.y1, 0],
  ]
    .map(([x, y, z]) => project(x, y, z).map((value) => value.toFixed(1)).join(","))
    .join(" ")

  return (
    <svg
      viewBox={`${view.left.toFixed(1)} ${view.top.toFixed(1)} ${view.width.toFixed(1)} ${view.height.toFixed(1)}`}
      role="img"
      aria-label={`${name}, drawn to its own ${widthCm} by ${depthCm} by ${heightCm} centimetres`}
      className={cn("h-full w-full", className)}
      preserveAspectRatio="xMidYMid meet"
    >
      <polygon points={shadow} fill="#000000" fillOpacity={0.28} />
      {showClearance && ask > 0 && (
        <polygon points={shadow} fill="none" stroke="currentColor" strokeOpacity={0.45} strokeWidth={widthCm * 0.008} strokeDasharray={`${widthCm * 0.05} ${widthCm * 0.04}`} />
      )}
      {drawn.map(({ box }, index) => {
        const part = boxes[index]
        const tone = part?.tone === "leg" ? mix(base, -0.55) : part?.tone === "linen" ? mix(base, 0.3) : base
        return (
          <g key={`${part?.label ?? "body"}-${index}`}>
            {(["left", "right", "top"] as const).map((which) => (
              <polygon
                key={which}
                points={face(box, which)}
                fill={mix(tone, SHADE[which])}
                stroke={mix(tone, SHADE[which] - 0.16)}
                strokeWidth={widthCm * 0.004}
                strokeLinejoin="round"
              />
            ))}
          </g>
        )
      })}
    </svg>
  )
}
