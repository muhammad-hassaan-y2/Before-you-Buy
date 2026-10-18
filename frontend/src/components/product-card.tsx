"use client"

import { Box, Camera, Sparkles } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { AddToBag } from "@/components/bag-drawer"
import { ProductIso } from "@/components/product-iso"
import { Badge } from "@/components/ui/badge"
import type { CatalogRow, StockRow } from "@/lib/api"
import { getProductImage } from "@/lib/product-images"
import { price, stockLine, stockTone, verdictLabel, verdictVariant } from "@/lib/store"
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

export function ProductCard({ row, verdict, simulationId, stock, roomWidthM, roomDepthM, roomHeightM }: Props) {
  const { commerce, geometry } = row
  const [viewMode, setViewMode] = useState<"photo" | "schematic">("photo")
  const variant = verdictVariant(verdict)
  const overruns = geometry.width_cm / 100 > roomWidthM || geometry.depth_cm / 100 > roomDepthM
  const image = getProductImage(row.sku, row.category)

  return (
    <article className="group flex flex-col overflow-hidden rounded-3xl border border-border bg-gradient-to-b from-card to-background shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-border hover:shadow-2xl hover:shadow-black/50">
      <div className="relative">
        <Link
          href={`/product/${row.sku}`}
          className="block rounded-3xl focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          {/* Top Hero Media Area */}
          <div className="relative flex h-60 w-full items-center justify-center overflow-hidden bg-surface px-6 pt-6">
            {/* Verdict Badge */}
            <Badge variant={variant} className="absolute top-4 left-4 z-10 bg-background/85 px-3.5 py-1.5 text-sm font-semibold shadow-md backdrop-blur-md">
              {verdictLabel(verdict)}
            </Badge>

            {/* Live Stock Status */}
            <p className={`absolute top-4 right-4 z-10 text-[11px] font-medium backdrop-blur-md rounded-full px-2 py-0.5 bg-background/40 border border-border ${stockTone(stock?.state)}`}>
              {stock ? stockLine(stock) : "reading the shelf…"}
            </p>

            {/* View Mode Content: Real Photo vs CAD Schematic */}
            {viewMode === "photo" ? (
              <div className="relative h-full w-full overflow-hidden rounded-2xl">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={image.url}
                  alt={image.alt}
                  className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
              </div>
            ) : (
              <div className="flex h-full w-full items-center justify-center py-2 transition-transform duration-500 group-hover:scale-[1.04]">
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

            {/* Dimensions HUD tag */}
            <p className="num absolute bottom-3 left-4 z-10 rounded-full border border-border bg-background/60 px-2 py-0.5 text-[10px] font-mono text-foreground/80 backdrop-blur-md">
              {geometry.width_cm.toFixed(0)} × {geometry.depth_cm.toFixed(0)} × {geometry.height_cm.toFixed(0)} cm
            </p>
          </div>
        </Link>

        {/* Photo vs 3D Schematic Toggle Button */}
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            setViewMode((m) => (m === "photo" ? "schematic" : "photo"))
          }}
          className="absolute bottom-3 right-4 z-20 flex items-center gap-1 rounded-full border border-border bg-background/70 px-2.5 py-1 text-[11px] font-medium text-foreground shadow-md backdrop-blur-md transition-colors hover:bg-foreground/20"
        >
          {viewMode === "photo" ? (
            <>
              <Box className="size-3 text-primary" /> 3D CAD
            </>
          ) : (
            <>
              <Camera className="size-3 text-primary" /> Photo
            </>
          )}
        </button>
      </div>

      <Link href={`/product/${row.sku}`} className="px-5 pt-4 pb-2">
        <div className="flex items-center justify-between gap-2">
          <p className="eyebrow truncate text-muted-foreground">
            {row.brand} · {row.category}
          </p>
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground font-mono">
            <Sparkles className="size-2.5 text-primary" /> AI Verified
          </span>
        </div>
        <h3 className="display mt-1 truncate text-lg text-foreground group-hover:text-primary transition-colors">
          {row.name}
        </h3>
        <p className="mt-1 flex flex-wrap items-baseline gap-x-2">
          <span className="num text-2xl font-semibold tracking-tight text-foreground">{price(commerce.retail_eur)}</span>
          <span className="text-xs text-muted-foreground font-medium">+{commerce.margin_pct.toFixed(0)}% margin</span>
        </p>
      </Link>

      <dl className="mt-auto space-y-1.5 border-t border-border px-5 py-3.5 text-xs">
        {(
          [
            ["Ships", `${commerce.lead_days} days · ${commerce.freight} freight`, null],
            ["Sold by", `${commerce.supplier.name} · ${commerce.supplier.region}`, null],
            [
              "In a",
              `${roomWidthM} × ${roomDepthM} m room`,
              overruns ? "text-destructive font-medium" : verdict ? "text-foreground" : "text-muted-foreground",
            ],
          ] as const
        ).map(([labelText, value, tone]) => (
          <div key={labelText} className="flex items-baseline justify-between gap-3">
            <dt className="shrink-0 text-muted-foreground">{labelText}</dt>
            <dd className={tone ?? "min-w-0 truncate text-foreground/80"}>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="px-5 pb-5">
        <AddToBag
          sku={row.sku}
          simulationId={simulationId}
          verdict={verdict}
          room={{ width_m: roomWidthM, depth_m: roomDepthM, height_m: roomHeightM }}
          className="w-full rounded-full font-medium"
        />
      </div>
    </article>
  )
}
