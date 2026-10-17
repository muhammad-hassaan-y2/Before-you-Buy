"use client"

import Link from "next/link"

import { AddToBag } from "@/components/bag-drawer"
import { ProductFigure } from "@/components/product-figure"
import { Badge } from "@/components/ui/badge"
import type { CatalogRow } from "@/lib/api"
import { price, verdictLabel, verdictVariant } from "@/lib/store"

type Props = {
  row: CatalogRow
  /** The geometry engine's verdict for this piece in the room on screen, or undefined when the
   *  room has not been measured against it yet. */
  verdict?: string
  /** The simulation that produced that verdict. Bagging the piece with it attached means the bag
   *  inherits a proven line instead of paying a GPU job to reach the same answer again. */
  simulationId?: string | null
  roomWidthM: number
  roomDepthM: number
  roomHeightM: number
}

/** A card for a piece nobody has to guess about: the drawing is the catalog's own centimetres on
 *  the shopper's floor, and the price, margin and lead time are the catalog service's numbers. */
export function ProductCard({ row, verdict, simulationId, roomWidthM, roomDepthM, roomHeightM }: Props) {
  const { commerce, geometry } = row
  const variant = verdictVariant(verdict)
  const tone = variant === "success" || variant === "warning" ? "pass" : variant === "destructive" ? "fail" : "unmeasured"
  const overruns = geometry.width_cm / 100 > roomWidthM || geometry.depth_cm / 100 > roomDepthM

  return (
    <article className="group flex flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-xl hover:shadow-black/20">
      <Link
        href={`/product/${row.sku}`}
        className="rounded-2xl focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <div className="relative flex items-center justify-center bg-surface px-6 pt-6 pb-5">
          <Badge variant={variant} className="absolute top-4 left-4">
            {verdictLabel(verdict)}
          </Badge>
          <ProductFigure
            widthCm={geometry.width_cm}
            depthCm={geometry.depth_cm}
            clearanceCm={geometry.clearance_cm}
            roomWidthM={roomWidthM}
            roomDepthM={roomDepthM}
            tone={tone}
            name={row.name}
            className="max-w-[19rem] transition-transform duration-500 group-hover:scale-[1.015]"
          />
          <p className="num absolute right-4 bottom-2.5 text-[10px] text-muted-foreground">
            {roomWidthM} × {roomDepthM} m
          </p>
        </div>
        <div className="px-5 pb-1">
          <p className="eyebrow truncate text-muted-foreground">{row.brand} · {row.category}</p>
          <h3 className="mt-1.5 truncate text-[15px] font-semibold tracking-tight">{row.name}</h3>
          <p className="mt-1 flex flex-wrap items-baseline gap-x-2">
            <span className="num text-2xl font-semibold">{price(commerce.retail_eur)}</span>
            <span className="text-xs text-muted-foreground">+{commerce.margin_pct.toFixed(0)}% margin</span>
          </p>
        </div>
      </Link>

      <dl className="mt-auto space-y-1.5 border-t border-border/50 px-5 py-4 text-xs">
        {(
          [
            ["Ships", `${commerce.lead_days} days · ${commerce.freight} freight`, null],
            ["Sold by", `${commerce.supplier.name} · ${commerce.supplier.region}`, null],
            [
              "Box",
              `${geometry.width_cm.toFixed(0)} × ${geometry.depth_cm.toFixed(0)} × ${geometry.height_cm.toFixed(0)} cm${overruns ? " · larger than this room" : ""}`,
              overruns ? "text-destructive" : null,
            ],
          ] as const
        ).map(([labelText, value, tone]) => (
          <div key={labelText} className="flex items-baseline justify-between gap-3">
            <dt className="shrink-0 text-muted-foreground">{labelText}</dt>
            <dd className={tone ?? "min-w-0 truncate text-foreground"}>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="px-5 pb-5">
        <AddToBag
          sku={row.sku}
          simulationId={simulationId}
          verdict={verdict}
          room={{ width_m: roomWidthM, depth_m: roomDepthM, height_m: roomHeightM }}
          className="w-full"
        />
      </div>
    </article>
  )
}
