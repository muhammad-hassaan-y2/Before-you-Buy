"use client"

import { ArrowLeft, ExternalLink } from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"

import { AddToBag } from "@/components/bag-drawer"
import { ProductFigure } from "@/components/product-figure"
import { ProductSimulator } from "@/components/product-simulator"
import { Badge } from "@/components/ui/badge"
import { fetchProduct, type CatalogRow } from "@/lib/api"
import { useBag } from "@/lib/bag"
import { bandLabel, price } from "@/lib/store"

type Props = { sku: string }

/** One shelf of the shop, with the terms the catalog derived for it and a live simulation beside
 *  them — the price a shopper sees and the verdict they earn are on the same screen. */
export function ProductDetail({ sku }: Props) {
  const [row, setRow] = useState<CatalogRow | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { room } = useBag()
  const floor = { width: room?.width_m ?? 4, depth: room?.depth_m ?? 3.5 }

  useEffect(() => {
    let cancelled = false
    fetchProduct(sku).then(
      (found) => !cancelled && setRow(found),
      (caught: unknown) => !cancelled && setError(caught instanceof Error ? caught.message : `No listing for ${sku}`),
    )
    return () => {
      cancelled = true
    }
  }, [sku])

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10 lg:py-14">
      <Link href="/store" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
        <ArrowLeft className="size-3.5" /> Back to the shop
      </Link>

      {error && <p className="mt-6 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{error}</p>}

      {row && (
        <div className="mt-8 space-y-10">
          <header className="max-w-3xl">
            <p className="eyebrow text-primary">
              {row.brand} · {row.category}
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-[-0.03em] text-balance lg:text-5xl">{row.name}</h1>
            <p className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="num text-5xl font-semibold tracking-[-0.03em] lg:text-6xl">{price(row.commerce.retail_eur)}</span>
              <Badge variant="secondary">{bandLabel(row.price_band ?? "")}</Badge>
              <span className="text-sm text-muted-foreground">
                {row.material} · {row.geometry.width_cm.toFixed(0)} × {row.geometry.depth_cm.toFixed(0)} × {row.geometry.height_cm.toFixed(0)} cm
              </span>
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-4">
              <AddToBag sku={row.sku} size="lg" />
              <p className="max-w-sm text-xs text-muted-foreground">
                An unproven line is fine — the bag measures it. Nothing checks out until the geometry engine clears every piece in it.
              </p>
            </div>
          </header>

          <figure className="rounded-3xl border border-border/60 bg-surface px-8 py-8">
            <ProductFigure
              widthCm={row.geometry.width_cm}
              depthCm={row.geometry.depth_cm}
              clearanceCm={row.geometry.clearance_cm}
              roomWidthM={floor.width}
              roomDepthM={floor.depth}
              tone="unmeasured"
              name={row.name}
              className="mx-auto max-w-lg"
            />
            <figcaption className="mx-auto mt-4 max-w-md text-center text-xs text-muted-foreground">
              Its footprint to scale on a {floor.width} × {floor.depth} m floor —{" "}
              {room ? "the room you are shopping for" : "the room the shop assumes until you change it"} — drawn from the
              centimetres the catalog states, and moved by the same engine as the test below.
            </figcaption>
          </figure>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-start">
            <div>
              <h2 className="eyebrow text-muted-foreground">The terms on this piece</h2>
              <dl className="mt-4 divide-y divide-border/60 overflow-hidden rounded-2xl border border-border/60 bg-card">
                {(
                  [
                    ["Cost to the shop", price(row.commerce.cost_eur)],
                    ["Margin", `${price(row.commerce.margin_eur)} · ${row.commerce.margin_pct.toFixed(1)}%`],
                    ["Ships in", `${row.commerce.lead_days} days`],
                    ["Freight", `${row.commerce.freight} · ${row.commerce.volume_m3.toFixed(3)} m³`],
                    ["Sold by", `${row.commerce.supplier.name} · ${row.commerce.supplier.region}`],
                  ] as const
                ).map(([labelText, value]) => (
                  <div key={labelText} className="flex items-baseline justify-between gap-4 px-5 py-3.5">
                    <dt className="text-sm text-muted-foreground">{labelText}</dt>
                    <dd className="num text-right text-sm font-medium">{value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-4 text-xs text-muted-foreground">{row.commerce.basis}.</p>

              <div className="mt-6 flex flex-wrap items-center gap-2 rounded-xl border bg-muted/30 p-3 text-xs">
                <ExternalLink className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="text-muted-foreground">Listing this simulation reads:</span>
                <code className="min-w-0 flex-1 truncate font-mono">{row.commerce.product_url}</code>
              </div>
            </div>

            <ProductSimulator row={row} />
          </div>
        </div>
      )}
    </div>
  )}
