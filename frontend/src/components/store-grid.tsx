"use client"

import { Loader2, Ruler, Search, SlidersHorizontal } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { ProductCard } from "@/components/product-card"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { callTool, proofsOf, verdictsOf, type CatalogFits } from "@/lib/agent"
import { fetchCatalog, type CatalogRow } from "@/lib/api"
import { trackRoom } from "@/lib/bag"
import { bands, categories, EMPTY_FILTER, match, sortRows, type StoreFilter, type StoreSort } from "@/lib/store"
import { cn } from "@/lib/utils"

const SORTS: { key: StoreSort; label: string }[] = [
  { key: "fit", label: "Fit first" },
  { key: "price", label: "Price" },
  { key: "margin", label: "Margin" },
  { key: "lead", label: "Lead time" },
  { key: "size", label: "Box size" },
]

/** The most the shop will measure in one sweep. Above it, agent-service caps the fan-out. */
const MEASURE = 8

export function StoreGrid() {
  const [rows, setRows] = useState<CatalogRow[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [filter, setFilter] = useState<StoreFilter>(EMPTY_FILTER)
  const [width, setWidth] = useState("4.0")
  const [depth, setDepth] = useState("3.5")
  const [height, setHeight] = useState("2.4")
  const [fits, setFits] = useState<CatalogFits | null>(null)
  const [busy, setBusy] = useState(false)
  const [fitError, setFitError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchCatalog().then(
      (catalog) => {
        if (!cancelled) {
          setRows(catalog)
          setLoaded(true)
        }
      },
      (caught: unknown) => {
        if (!cancelled) setLoadError(caught instanceof Error ? caught.message : "catalog-service is not reachable.")
      },
    )
    return () => {
      cancelled = true
    }
  }, [])

  const verdicts = useMemo(() => (fits ? verdictsOf(fits) : {}), [fits])
  const proofs = useMemo(() => (fits ? proofsOf(fits) : {}), [fits])
  const visible = useMemo(() => sortRows(rows.filter((row) => match(row, filter)), filter, verdicts), [rows, filter, verdicts])
  const roomWidth = Number(width) || 4
  const roomDepth = Number(depth) || 3.5
  const roomHeight = Number(height) || 2.4

  // The bag is measured against the room the shopper was looking at, so the bar tells the bag
  // store what that room is. Lines already proven for another room go stale on their own.
  useEffect(() => {
    trackRoom({ width_m: roomWidth, depth_m: roomDepth, height_m: roomHeight })
  }, [roomWidth, roomDepth, roomHeight])

  async function measure() {
    setBusy(true)
    setFitError(null)
    try {
      setFits(
        await callTool<CatalogFits>("fit_catalog", {
          room_width_m: roomWidth,
          room_depth_m: roomDepth,
          room_height_m: roomHeight,
          category: filter.category,
          price_band: filter.priceBand,
          query: filter.query,
          limit: MEASURE,
        }),
      )
    } catch (caught) {
      setFits(null)
      setFitError(caught instanceof Error ? caught.message : "The fit sweep did not return.")
    } finally {
      setBusy(false)
    }
  }

  function patch(next: Partial<StoreFilter>) {
    setFilter((current) => ({ ...current, ...next }))
  }

  if (loadError) {
    return (
      <p className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{loadError}</p>
    )
  }
  if (!loaded) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Opening the shop…
      </div>
    )
  }

  const chips = (options: string[], selected: string | null, key: "category" | "priceBand") => (
    <div className="flex flex-wrap gap-1.5">
      <Button type="button" size="sm" variant={selected === null ? "default" : "outline"} aria-pressed={selected === null} onClick={() => patch({ [key]: null } as Partial<StoreFilter>)}>
        All
      </Button>
      {options.map((option) => (
        <Button
          key={option}
          type="button"
          size="sm"
          variant={selected === option ? "default" : "outline"}
          aria-pressed={selected === option}
          onClick={() => patch({ [key]: selected === option ? null : option } as Partial<StoreFilter>)}
        >
          {option}
        </Button>
      ))}
    </div>
  )

  return (
    <div className="space-y-8">
      <Card className="overflow-hidden border-border/60 bg-gradient-to-b from-card to-muted/40">
        <CardContent className="grid gap-5 p-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div className="space-y-3">
            <Label htmlFor="room-width" className="text-xs tracking-[0.14em] text-muted-foreground uppercase">
              Your room
            </Label>
            <div className="grid max-w-sm grid-cols-3 gap-3">
              {(
                [
                  ["Width", width, setWidth, "room-width"],
                  ["Depth", depth, setDepth, "room-depth"],
                  ["Height", height, setHeight, "room-height"],
                ] as const
              ).map(([labelText, value, setter, id]) => (
                <div key={id} className="space-y-1.5">
                  <Label htmlFor={id} className="text-xs text-muted-foreground">
                    {labelText} (m)
                  </Label>
                  <Input id={id} inputMode="decimal" value={value} onChange={(event) => setter(event.target.value)} disabled={busy} className="text-center" />
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              {fits
                ? `${fits.checked} pieces measured in a ${fits.room.width_m} × ${fits.room.depth_m} m room — ${fits.fits.length} fit, ${fits.does_not_fit.length} do not.`
                : `Measure the best ${MEASURE} candidates in this room. The geometry worker settles every verdict; nothing here is guessed.`}
            </p>
          </div>
          <div className="space-y-2">
            <Button size="lg" onClick={measure} disabled={busy}>
              {busy ? <Loader2 className="animate-spin" /> : <Ruler className="size-4" />}
              {busy ? "Measuring…" : "Measure in my room"}
            </Button>
            {fitError && <p className="max-w-xs text-xs text-destructive">{fitError}</p>}
          </div>
        </CardContent>
      </Card>

      {fits && <p className="max-w-3xl text-xs text-muted-foreground">{fits.note}</p>}

      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="space-y-3">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={filter.query}
              onChange={(event) => patch({ query: event.target.value })}
              placeholder="linen, oak, deep seat…"
              className="rounded-full bg-background/60 pl-9"
              aria-label="Search the catalog"
            />
          </div>
          {chips(categories(rows), filter.category, "category")}
          {chips(bands(rows), filter.priceBand, "priceBand")}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <SlidersHorizontal className="size-3.5" />
          <Label htmlFor="sort" className="sr-only">
            Sort by
          </Label>
          <select
            id="sort"
            value={filter.sort}
            onChange={(event) => patch({ sort: event.target.value as StoreSort })}
            className={cn("h-9 rounded-full border border-input bg-background/60 px-3 text-xs text-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50")}
          >
            {SORTS.map((sort) => (
              <option key={sort.key} value={sort.key}>
                {sort.label}
              </option>
            ))}
          </select>
          <span className="tabular-nums">{visible.length === 1 ? "1 piece" : `${visible.length} pieces`}</span>
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          Nothing in the shop matches that. Clear a filter and try again.
        </p>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((row) => (
            <ProductCard
              key={row.sku}
              row={row}
              verdict={verdicts[row.sku]}
              simulationId={proofs[row.sku]}
              roomWidthM={roomWidth}
              roomDepthM={roomDepth}
              roomHeightM={roomHeight}
            />
          ))}
        </div>
      )}
    </div>
  )
}
