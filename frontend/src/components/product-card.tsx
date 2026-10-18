"use client"

import Link from "next/link"
import { useState } from "react"

import { AddToBag } from "@/components/bag-drawer"
import { ProductIso } from "@/components/product-iso"
import type { CatalogRow, StockRow } from "@/lib/api"
import { getProductImage } from "@/lib/product-images"
import { FootprintPlan, LeadBar, StockDots } from "@/components/visuals"
import { price, verdictLabel } from "@/lib/store"
import { cn } from "@/lib/utils"

type Props = {
  row: CatalogRow
  verdict?: string
  simulationId?: string | null
  stock?: StockRow
  roomWidthM: number
  roomDepthM: number
  roomHeightM: number
}

const VERDICT_BAR: Record<string, string> = {
  fits: "bg-success/12 text-success",
  tight: "bg-warning/15 text-warning",
  too_large: "bg-destructive/12 text-destructive",
  blocked: "bg-destructive/12 text-destructive",
}

/** A catalogue entry, not a tile: picture, the engine's verdict as a full-width bar, then the
 *  piece set out in ruled lines. No frame around the whole thing; the rule below separates it. */
export function ProductCard({ row, verdict, simulationId, stock, roomWidthM, roomDepthM, roomHeightM }: Props) {
  const { commerce, geometry } = row
  const [viewMode, setViewMode] = useState<"photo" | "schematic">("photo")
  const overruns = geometry.width_cm / 100 > roomWidthM || geometry.depth_cm / 100 > roomDepthM
  const image = getProductImage(row.sku, row.category)

  return (
    <article className="group flex flex-col">
      <Link
        href={`/product/${row.sku}`}
        className="block overflow-hidden rounded-md focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <div className="relative flex aspect-[4/3] w-full items-center justify-center overflow-hidden bg-surface">
          {viewMode === "photo" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={image.url}
              alt={image.alt}
              className="h-full w-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.03]"
              loading="lazy"
            />
          ) : (
            <div className="h-full w-full p-6">
              <ProductIso
                parts={row.parts}
                widthCm={geometry.width_cm}
                depthCm={geometry.depth_cm}
                heightCm={geometry.height_cm}
                clearanceCm={geometry.clearance_cm}
                material={row.material}
                name={row.name}
              />
            </div>
          )}
        </div>
      </Link>

      <div
        role="status"
        data-verdict={verdict ?? "none"}
        className={cn(
          "mt-3 flex items-center justify-between gap-3 rounded-md px-3 py-2 text-sm font-semibold",
          verdict ? (VERDICT_BAR[verdict] ?? "bg-muted text-muted-foreground") : "bg-muted text-muted-foreground",
        )}
      >
        <span className="flex items-center gap-2">
          <span aria-hidden className="size-2 rounded-full bg-current" />
          {verdictLabel(verdict)}
        </span>
        <span className="num text-xs font-normal opacity-80">
          {roomWidthM} × {roomDepthM} m room
        </span>
      </div>

      <Link href={`/product/${row.sku}`} className="mt-4 block focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
        <p className="eyebrow truncate text-muted-foreground">
          {row.brand} · {row.category}
        </p>
        <h3 className="display mt-1 truncate text-xl text-foreground transition-colors group-hover:text-primary">{row.name}</h3>
        <p className="num mt-1 text-xl font-semibold text-foreground">{price(commerce.retail_eur)}</p>
      </Link>

      <div className="mt-4 grid grid-cols-[minmax(0,5fr)_minmax(0,6fr)] items-center gap-4 border-y border-border py-4">
        <figure>
          <FootprintPlan roomW={roomWidthM} roomD={roomDepthM} pieceWcm={geometry.width_cm} pieceDcm={geometry.depth_cm} verdict={verdict} />
          <figcaption className={cn("num mt-1.5 text-center text-[11px]", overruns ? "font-medium text-destructive" : "text-muted-foreground")}>
            {geometry.width_cm.toFixed(0)} × {geometry.depth_cm.toFixed(0)} × {geometry.height_cm.toFixed(0)} cm
          </figcaption>
        </figure>
        <dl className="space-y-3 text-xs">
          <div>
            <dt className="eyebrow text-muted-foreground">On the floor</dt>
            <dd className="mt-1.5">
              <StockDots stock={stock} />
            </dd>
          </div>
          <div>
            <dt className="eyebrow text-muted-foreground">Ships</dt>
            <dd className="mt-1.5">
              <LeadBar days={commerce.lead_days} />
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <AddToBag
          sku={row.sku}
          simulationId={simulationId}
          verdict={verdict}
          room={{ width_m: roomWidthM, depth_m: roomDepthM, height_m: roomHeightM }}
          className="flex-1 rounded-full font-medium"
        />
        <button
          type="button"
          onClick={() => setViewMode((mode) => (mode === "photo" ? "schematic" : "photo"))}
          className="shrink-0 px-1 text-xs text-muted-foreground underline underline-offset-4 transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {viewMode === "photo" ? "Schematic" : "Photo"}
        </button>
      </div>
    </article>
  )
}
