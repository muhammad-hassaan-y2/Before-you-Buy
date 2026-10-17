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
import { bandLabel, bands, categories, EMPTY_FILTER, match, sortRows, type StoreFilter, type StoreSort } from "@/lib/store"
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

  const chip = (label: string, selected: boolean, onClick: () => void) => (
    <Button
      key={label}
      type="button"
      size="sm"
      variant={selected ? "default" : "outline"}
      aria-pressed={selected}
      className="rounded-full"
      onClick={onClick}
    >
      {label}
    </Button>
  )

  return (
    <div className="space-y-8">
      <Card className="border-border/60 bg-surface">
        <CardContent className="p-6">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-4">
            <Label htmlFor="room-width" className="eyebrow text-muted-foreground">
              The room you are shopping for
            </Label>
            <div className="flex items-center gap-2">
              {(
                [
                  ["Width", width, setWidth, "room-width"],
                  ["Depth", depth, setDepth, "room-depth"],
                  ["Height", height, setHeight, "room-height"],
                ] as const
              ).map(([labelText, value, setter, id], at) => (
                <div key={id} className="flex items-center gap-2">
                  {at > 0 && <span aria-hidden className="text-muted-foreground">×</span>}
                  <Label htmlFor={id} className="sr-only">
                    {labelText} in metres
                  </Label>
                  <Input
                    id={id}
                    inputMode="decimal"
                    value={value}
                    onChange={(event) => setter(event.target.value)}
                    disabled={busy}
                    className="num w-[4.5rem] bg-background/70 text-center font-semibold"
                  />
                </div>
              ))}
              <span className="text-xs text-muted-foreground">m · width × depth × height</span>
            </div>
            <Button size="lg" className="ml-auto" onClick={measure} disabled={busy}>
              {busy ? <Loader2 className="animate-spin" /> : <Ruler className="size-4" />}
              {busy ? "Measuring…" : "Measure in my room"}
            </Button>
          </div>
          <p className="mt-4 border-t border-border/50 pt-3.5 text-xs text-muted-foreground">
            {fits
              ? `${fits.checked} pieces measured in a ${fits.room.width_m} × ${fits.room.depth_m} m room — ${fits.fits.length} fit, ${fits.does_not_fit.length} do not.`
              : `Measure the best ${MEASURE} candidates in this room. The geometry worker settles every verdict; nothing here is guessed.`}
            {fitError && <span className="text-destructive"> {fitError}</span>}
          </p>
        </CardContent>
      </Card>

      {fits && <p className="max-w-3xl text-xs text-muted-foreground">{fits.note}</p>}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
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
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by category">
          {chip("Everything", filter.category === null, () => patch({ category: null }))}
          {categories(rows).map((option) =>
            chip(option, filter.category === option, () => patch({ category: filter.category === option ? null : option })),
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by price tier">
          {chip("Any price", filter.priceBand === null, () => patch({ priceBand: null }))}
          {bands(rows).map((option) =>
            chip(bandLabel(option), filter.priceBand === option, () =>
              patch({ priceBand: filter.priceBand === option ? null : option }),
            ),
          )}
        </div>
        <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
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
          <span className="num">{visible.length === 1 ? "1 piece" : `${visible.length} pieces`}</span>
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          Nothing in the shop matches that. Clear a filter and try again.
        </p>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
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
