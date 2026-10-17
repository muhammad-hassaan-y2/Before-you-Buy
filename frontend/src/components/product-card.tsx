import Link from "next/link"
import { Clock, Package, Store } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { CatalogRow } from "@/lib/api"
import { price, verdictLabel, verdictVariant } from "@/lib/store"

type Props = {
  row: CatalogRow
  /** The geometry engine's verdict for this piece in the room on screen, or undefined when the
   *  room has not been measured against it yet. */
  verdict?: string
  roomWidthM: number
  roomDepthM: number
}

/** Drawing units per metre. The plan is small, so the room is padded rather than cropped. */
const UNITS_PER_M = 24
const PAD_M = 0.25

/** A card for a piece nobody has to guess about: the price, the margin and the lead time are the
 *  catalog service's own numbers, and the drawing is the box to scale on the shopper's floor. */
export function ProductCard({ row, verdict, roomWidthM, roomDepthM }: Props) {
  const { commerce, geometry } = row
  const pad = PAD_M * UNITS_PER_M
  const viewW = roomWidthM * UNITS_PER_M + pad * 2
  const viewH = roomDepthM * UNITS_PER_M + pad * 2
  const itemW = Math.min((geometry.width_cm / 100) * UNITS_PER_M, viewW - pad * 2)
  const itemD = Math.min((geometry.depth_cm / 100) * UNITS_PER_M, viewH - pad * 2)
  const clearance = (geometry.clearance_cm / 100) * UNITS_PER_M
  // Where it would actually stand: against the back wall, off to one side, so the bare floor in
  // front of it reads as the walkway the verdict is about.
  const x = pad + 2
  const y = pad + 2
  const overruns = geometry.width_cm / 100 > roomWidthM || geometry.depth_cm / 100 > roomDepthM

  const fill = !verdict
    ? "fill-room-product/40 stroke-room-product"
    : verdictVariant(verdict) === "destructive"
      ? "fill-destructive/35 stroke-destructive"
      : "fill-success/30 stroke-success"

  return (
    <Link
      href={`/product/${row.sku}`}
      className="group flex flex-col gap-4 rounded-2xl border border-border/60 bg-card p-5 text-card-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-xl hover:shadow-black/20 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <div className="flex items-start gap-4">
        <figure className="shrink-0 rounded-xl border border-border/60 bg-muted/40 p-2">
          <svg
            viewBox={`0 0 ${viewW.toFixed(1)} ${viewH.toFixed(1)}`}
            className="h-auto w-20"
            role="img"
            aria-label={`${row.name} footprint in a ${roomWidthM} by ${roomDepthM} metre room`}
          >
            <rect
              x={pad}
              y={pad}
              width={(roomWidthM * UNITS_PER_M).toFixed(1)}
              height={(roomDepthM * UNITS_PER_M).toFixed(1)}
              rx="2"
              className="fill-room-floor/15 stroke-muted-foreground/40"
              strokeWidth="1"
            />
            {clearance >= 1.5 && (
              <rect
                x={(x - clearance).toFixed(1)}
                y={(y - clearance).toFixed(1)}
                width={(itemW + clearance * 2).toFixed(1)}
                height={(itemD + clearance * 2).toFixed(1)}
                rx="2"
                className="fill-none stroke-muted-foreground/45"
                strokeWidth="0.8"
                strokeDasharray="2.5 2.5"
              />
            )}
            <rect x={x} y={y} width={itemW.toFixed(1)} height={itemD.toFixed(1)} rx="1.5" className={fill} strokeWidth="1.2" />
          </svg>
          <figcaption className="mt-1 text-center font-mono text-[10px] tabular-nums text-muted-foreground">
            {roomWidthM} × {roomDepthM} m
          </figcaption>
        </figure>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 truncate text-[11px] tracking-[0.14em] text-muted-foreground uppercase">
              {row.brand} · {row.category}
            </p>
            <Badge variant={verdictVariant(verdict)} className="shrink-0">
              {verdictLabel(verdict)}
            </Badge>
          </div>
          <h3 className="mt-1 truncate text-base font-semibold tracking-tight">{row.name}</h3>
          <p className="mt-2 font-mono text-2xl tabular-nums">
            {price(commerce.retail_eur)}
            <span className="ml-1.5 align-middle text-xs text-muted-foreground">+{commerce.margin_pct.toFixed(0)}% margin</span>
          </p>
        </div>
      </div>

      <dl className="grid gap-1.5 border-t border-border/50 pt-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <Clock className="size-3.5 shrink-0" />
          <dt className="sr-only">Lead time</dt>
          <dd>
            {commerce.lead_days} days, {commerce.freight} freight
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <Store className="size-3.5 shrink-0" />
          <dt className="sr-only">Supplier</dt>
          <dd className="truncate">
            {commerce.supplier.name} · {commerce.supplier.region}
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <Package className="size-3.5 shrink-0" />
          <dt className="sr-only">Box</dt>
          <dd className="truncate">
            {geometry.width_cm.toFixed(0)} × {geometry.depth_cm.toFixed(0)} × {geometry.height_cm.toFixed(0)} cm
            {overruns && <span className="text-destructive"> · larger than this room</span>}
          </dd>
        </div>
      </dl>
    </Link>
  )
}
