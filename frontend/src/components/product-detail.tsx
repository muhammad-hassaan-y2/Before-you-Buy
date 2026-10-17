"use client"

import { ArrowLeft, ExternalLink } from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"

import { AddToBag } from "@/components/bag-drawer"
import { ProductSimulator } from "@/components/product-simulator"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { fetchProduct, type CatalogRow } from "@/lib/api"
import { price } from "@/lib/store"

type Props = { sku: string }

/** One shelf of the shop, with the terms the catalog derived for it and a live simulation beside
 *  them — the price a shopper sees and the verdict they earn are on the same screen. */
export function ProductDetail({ sku }: Props) {
  const [row, setRow] = useState<CatalogRow | null>(null)
  const [error, setError] = useState<string | null>(null)

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
        <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="lg:sticky lg:top-24 lg:self-start">
            <p className="text-xs tracking-[0.18em] text-primary uppercase">
              {row.brand} · {row.category}
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-balance">{row.name}</h1>
            <p className="mt-4 flex flex-wrap items-baseline gap-3">
              <span className="font-mono text-5xl tabular-nums">{price(row.commerce.retail_eur)}</span>
              <Badge variant="secondary">{row.price_band}</Badge>
              <span className="text-sm text-muted-foreground">
                {row.material} · {row.geometry.width_cm.toFixed(0)} × {row.geometry.depth_cm.toFixed(0)} × {row.geometry.height_cm.toFixed(0)} cm
              </span>
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <AddToBag sku={row.sku} size="lg" />
              <p className="max-w-xs text-xs text-muted-foreground">
                An unproven line is fine — the bag measures it. Nothing checks out until the geometry engine clears every piece in it.
              </p>
            </div>

            <Card className="mt-8">
              <CardContent className="p-6">
                <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
                {(
                  [
                    ["Cost to the shop", price(row.commerce.cost_eur)],
                    ["Margin", `${price(row.commerce.margin_eur)} · ${row.commerce.margin_pct.toFixed(1)}%`],
                    ["Ships in", `${row.commerce.lead_days} days`],
                    ["Freight", `${row.commerce.freight} · ${row.commerce.volume_m3.toFixed(3)} m³`],
                    ["Sold by", `${row.commerce.supplier.name} · ${row.commerce.supplier.region}`],
                    ["Price band", row.price_band ?? "—"],
                  ] as const
                ).map(([labelText, value]) => (
                  <div key={labelText}>
                    <dt className="text-xs tracking-[0.12em] text-muted-foreground uppercase">{labelText}</dt>
                    <dd className="mt-1 font-mono text-sm tabular-nums">{value}</dd>
                  </div>
                ))}
                </dl>
              </CardContent>
            </Card>

            <p className="mt-4 text-xs text-muted-foreground">{row.commerce.basis}.</p>

            <div className="mt-6 flex flex-wrap items-center gap-2 rounded-xl border bg-muted/30 p-3 text-xs">
              <ExternalLink className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="text-muted-foreground">Listing this simulation reads:</span>
              <code className="min-w-0 flex-1 truncate font-mono">{row.commerce.product_url}</code>
            </div>
          </div>

          <ProductSimulator row={row} />
        </div>
      )}
    </div>
  )}
