"use client"

import { ArrowLeft, ArrowRight, Box, Camera, Compass, ExternalLink, RefreshCw } from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"

import { AddToBag } from "@/components/bag-drawer"
import { ProductFigure } from "@/components/product-figure"
import { ProductIso } from "@/components/product-iso"
import { ProductSimulator } from "@/components/product-simulator"
import { ShelfPulse } from "@/components/shelf-pulse"
import { Badge } from "@/components/ui/badge"
import { fetchCatalog, fetchProduct, type CatalogRow } from "@/lib/api"
import { useBag } from "@/lib/bag"
import { useShelf } from "@/lib/live"
import { getProductImage } from "@/lib/product-images"
import { bandLabel, price, stockLine, stockTone } from "@/lib/store"
import { cn } from "@/lib/utils"

type Props = { sku: string }

const arrival = (days: number) =>
  new Date(Date.now() + days * 86_400_000).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })

export function ProductDetail({ sku }: Props) {
  const [row, setRow] = useState<CatalogRow | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [alsoIn, setAlsoIn] = useState<CatalogRow[]>([])
  const [mediaView, setMediaView] = useState<"photo" | "iso" | "floor">("photo")
  const { room } = useBag()
  const floor = { width: room?.width_m ?? 4, depth: room?.depth_m ?? 3.5 }
  const shelf = useShelf(15_000)

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

  useEffect(() => {
    if (!row) return
    let cancelled = false
    fetchCatalog().then(
      (catalog) => {
        if (cancelled) return
        setAlsoIn(catalog.filter((item) => item.category === row.category && item.sku !== row.sku).slice(0, 4))
      },
      () => !cancelled && setAlsoIn([]),
    )
    return () => {
      cancelled = true
    }
  }, [row])

  const stock = shelf.bySku[sku]
  const image = getProductImage(row?.sku, row?.category)

  const terms = row
    ? ([
        ["Cost to the shop", price(row.commerce.cost_eur)],
        ["Margin", `${price(row.commerce.margin_eur)} · ${row.commerce.margin_pct.toFixed(1)}%`],
        ["Ships in", `${row.commerce.lead_days} days`],
        ["Freight", `${row.commerce.freight} · ${row.commerce.volume_m3.toFixed(3)} m³`],
        ["Sold by", `${row.commerce.supplier.name} · ${row.commerce.supplier.region}`],
      ] as const)
    : []

  return (
    <div className="w-full">
      {error && (
        <div className="mx-auto w-full max-w-6xl px-6 py-10">
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{error}</p>
          <Link href="/store" className="mt-6 inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
            <ArrowLeft className="size-3.5" /> Back to the shop
          </Link>
        </div>
      )}

      {row && (
        <>
          {/* Apple-style Persistent Top Floating Bar */}
          <div className="sticky top-[3.25rem] z-30 border-b border-border bg-background/80">
            <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-2.5">
              <div className="flex items-center gap-3">
                <span className="font-semibold text-sm text-foreground">{row.name}</span>
                <span className="num font-semibold text-sm text-foreground">{price(row.commerce.retail_eur)}</span>
                <span className={`text-xs ${stockTone(stock?.state)}`}>
                  {stock ? stockLine(stock) : "reading the shelf…"}
                </span>
              </div>
              <AddToBag sku={row.sku} size="sm" className="rounded-full" />
            </div>
          </div>

          <section className="relative border-b border-border">
            <div className="mx-auto grid w-full max-w-7xl gap-10 px-6 pt-10 pb-14 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-center lg:pt-14 lg:pb-20">
              {/* Media Viewport with View Switcher */}
              <div className="order-2 flex flex-col lg:order-1">
                <div className="relative flex h-80 items-center justify-center overflow-hidden rounded-lg border border-border bg-surface p-6 lg:h-[440px]">
                  {/* View Mode Toggle Pill */}
                  <div className="absolute top-4 left-4 z-20 flex items-center rounded-full border border-border bg-background/70 p-1">
                    <button
                      type="button"
                      onClick={() => setMediaView("photo")}
                      className={cn(
                        "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all",
                        mediaView === "photo" ? "bg-foreground text-background shadow-sm" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <Camera className="size-3" /> Photo
                    </button>
                    <button
                      type="button"
                      onClick={() => setMediaView("iso")}
                      className={cn(
                        "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all",
                        mediaView === "iso" ? "bg-foreground text-background shadow-sm" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <Box className="size-3" /> 3D Clearance
                    </button>
                    <button
                      type="button"
                      onClick={() => setMediaView("floor")}
                      className={cn(
                        "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all",
                        mediaView === "floor" ? "bg-foreground text-background shadow-sm" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <Compass className="size-3" /> Room Fit
                    </button>
                  </div>


                  {/* Media Content */}
                  {mediaView === "photo" ? (
                    <div className="relative h-full w-full overflow-hidden rounded-lg">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={image.url}
                        alt={image.alt}
                        className="h-full w-full object-cover transition-transform duration-700 ease-out hover:scale-105"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent pointer-events-none" />
                      <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between text-xs text-foreground/80">
                        <span className="font-mono bg-background/60 px-2.5 py-1 rounded-full border border-border backdrop-blur-md">
                          {row.geometry.width_cm} × {row.geometry.depth_cm} × {row.geometry.height_cm} cm
                        </span>
                        <span className="font-medium bg-background/60 px-2.5 py-1 rounded-full border border-border backdrop-blur-md">
                          {row.material}
                        </span>
                      </div>
                    </div>
                  ) : mediaView === "iso" ? (
                    <div className="h-64 w-full max-w-md transition-transform duration-700 ease-out lg:h-80">
                      <ProductIso
                        parts={row.parts}
                        widthCm={row.geometry.width_cm}
                        depthCm={row.geometry.depth_cm}
                        heightCm={row.geometry.height_cm}
                        clearanceCm={row.geometry.clearance_cm}
                        material={row.material}
                        showClearance
                        name={row.name}
                      />
                    </div>
                  ) : (
                    <div className="h-64 w-full max-w-md p-4 lg:h-80 flex items-center justify-center">
                      <ProductFigure
                        widthCm={row.geometry.width_cm}
                        depthCm={row.geometry.depth_cm}
                        clearanceCm={row.geometry.clearance_cm}
                        roomWidthM={floor.width}
                        roomDepthM={floor.depth}
                        tone="pass"
                        name={row.name}
                      />
                    </div>
                  )}
                </div>

                <figcaption className="mt-3 text-xs text-muted-foreground">
                  Drawn from the {row.geometry.width_cm.toFixed(0)} × {row.geometry.depth_cm.toFixed(0)} ×{" "}
                  {row.geometry.height_cm.toFixed(0)} cm catalog specifications. Dashed outline indicates manufacturer clearance buffer.
                </figcaption>
              </div>

              {/* Product Info & Action Area */}
              <div className="order-1 lg:order-2">
                <Link href="/store" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
                  <ArrowLeft className="size-3.5" /> Back to the shop
                </Link>
                <div className="mt-5 flex items-center gap-2">
                  <span className="eyebrow text-primary">
                    {row.brand} · {row.category}
                  </span>
                  <span className="text-muted-foreground">·</span>
                  <span className="font-mono text-xs text-muted-foreground">{row.sku}</span>
                </div>
                <h1 className="display mt-2 text-4xl text-foreground text-balance lg:text-5xl">
                  {row.name}
                </h1>
                <p className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="num text-4xl font-semibold tracking-tight text-foreground">{price(row.commerce.retail_eur)}</span>
                  <Badge variant="secondary" className="bg-foreground/10 text-foreground/80">{bandLabel(row.price_band ?? "")}</Badge>
                </p>
                <p className={`mt-4 text-sm font-medium ${stockTone(stock?.state)}`}>
                  {stock ? stockLine(stock) : "Reading the shelf…"}
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  Est. arrival {arrival(row.commerce.lead_days)}
                  <span aria-hidden>·</span>
                  <ShelfPulse live={shelf.live} counts={Object.keys(shelf.bySku).length} />
                  <button
                    type="button"
                    onClick={() => shelf.refresh()}
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    <RefreshCw className="size-3" /> re-read
                  </button>
                </p>

                <div className="mt-8 flex flex-wrap items-center gap-4">
                  <AddToBag sku={row.sku} size="lg" className="rounded-full px-6 py-2.5 font-medium" />
                  <p className="max-w-xs text-xs text-muted-foreground">
                    Guaranteed fit: add to bag and the spatial engine measures clearances across your real floor plan before checkout.
                  </p>
                </div>

                <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-border pt-6">
                  {(
                    [
                      ["Footprint", `${row.geometry.width_cm.toFixed(0)} × ${row.geometry.depth_cm.toFixed(0)} cm`],
                      ["Height", `${row.geometry.height_cm.toFixed(0)} cm`],
                      ["Clearance buffer", `${row.geometry.clearance_cm.toFixed(0)} cm all round`],
                      ["Volume", `${row.commerce.volume_m3.toFixed(3)} m³ · ${row.commerce.freight}`],
                    ] as const
                  ).map(([labelText, value]) => (
                    <div key={labelText}>
                      <dt className="eyebrow text-muted-foreground">{labelText}</dt>
                      <dd className="num mt-1 text-sm font-medium text-foreground">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </section>

          {/* Dropship Terms & Simulation Grid */}
          <div className="mx-auto w-full max-w-7xl px-6 py-10 space-y-12">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-start">
              <div className="rounded-lg border border-border p-6">
                <h2 className="eyebrow text-muted-foreground">The terms on this piece</h2>
                <dl className="mt-4 divide-y divide-border overflow-hidden rounded-lg border border-border bg-background/40">
                  {terms.map(([labelText, value]) => (
                    <div key={labelText} className="flex items-baseline justify-between gap-4 px-5 py-3.5">
                      <dt className="text-sm text-muted-foreground">{labelText}</dt>
                      <dd className="num text-right text-sm font-medium text-foreground">{value}</dd>
                    </div>
                  ))}
                </dl>
                <p className="mt-4 text-xs text-muted-foreground">{row.commerce.basis}.</p>

                <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-border pt-4 text-xs">
                  <ExternalLink className="size-3.5 shrink-0 text-muted-foreground" />
                  <span className="text-muted-foreground">Listing this simulation reads:</span>
                  <code className="min-w-0 flex-1 truncate font-mono text-foreground/80">{row.commerce.product_url}</code>
                </div>
              </div>

              <div className="rounded-lg border border-border p-6">
                <h2 className="text-xl font-semibold tracking-tight text-foreground mb-2">Live Room Fit Test</h2>
                <p className="text-sm text-muted-foreground mb-6">
                  Test this piece live in your room. The geometry worker validates door clearance, wall offsets, and walkway buffers.
                </p>
                <ProductSimulator row={row} />
              </div>
            </div>

            {/* Related items */}
            {alsoIn.length > 0 && (
              <section className="border-t border-border pt-10">
                <h2 className="eyebrow text-muted-foreground">More on the {row.category} shelf</h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {alsoIn.map((item) => {
                    const itemImage = getProductImage(item.sku, item.category)
                    return (
                      <Link
                        key={item.sku}
                        href={`/product/${item.sku}`}
                        className="group flex items-center gap-4 rounded-lg border border-border bg-card/60 p-3.5 transition-colors hover:bg-muted/50"
                      >
                        <div className="relative size-16 shrink-0 overflow-hidden rounded-md border border-border bg-background">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={itemImage.url}
                            alt={item.name}
                            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
                          />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-foreground group-hover:text-primary transition-colors">{item.name}</p>
                          <p className="num text-xs text-muted-foreground mt-0.5">{price(item.commerce.retail_eur)}</p>
                        </div>
                        <ArrowRight className="ml-auto size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                      </Link>
                    )
                  })}
                </div>
              </section>
            )}
          </div>
        </>
      )}
    </div>
  )
}
