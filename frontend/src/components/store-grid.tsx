"use client"

import { Activity, ArrowDown, Loader2, Radio, Ruler, Search, Square, StopCircle } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { ProductCard } from "@/components/product-card"
import { ShelfPulse } from "@/components/shelf-pulse"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { fetchCatalog, type CatalogRow } from "@/lib/api"
import { trackRoom } from "@/lib/bag"
import { streamSweep, useShelf, type SweepEvent } from "@/lib/live"
import {
  ago,
  bandLabel,
  bands,
  EMPTY_FILTER,
  match,
  price,
  sortRows,
  STOCK_LABEL,
  stockTone,
  type StoreFilter,
  type StoreSort,
} from "@/lib/store"
import { cn } from "@/lib/utils"
import { validateRoom } from "@/lib/validate"

const SORTS: { key: StoreSort; label: string }[] = [
  { key: "fit", label: "Fit first" },
  { key: "price", label: "Price" },
  { key: "margin", label: "Margin" },
  { key: "lead", label: "Lead time" },
  { key: "size", label: "Box size" },
]

/** The most the shop measures in one sweep. Above it, agent-service caps the fan-out. */
const MEASURE = 8

/** The shop's own traffic, read from the shelf rather than written as copy: what a hold or an
 *  order draft took off it, newest first. Empty is a real state, and it says so. */
function ShelfActivity({ events, rows }: { events: { at: string; action: string; sku: string; qty: number }[]; rows: CatalogRow[] }) {
  const name = (sku: string) => rows.find((row) => row.sku === sku)?.name ?? sku
  return (
    <div className="flex items-center gap-3 overflow-hidden border-y border-border py-2 text-xs">
      <Radio className="size-3.5 shrink-0 text-primary" />
      {events.length === 0 ? (
        <span className="truncate text-muted-foreground">Nothing has moved on the shelf yet — a hold or an order draft is what changes a count here.</span>
      ) : (
        <span className="truncate">
          <span className={events[0].action === "claimed" ? "font-medium text-warning" : "font-medium text-success"}>
            {events[0].action === "claimed" ? "Held" : "Released"}
          </span>{" "}
          <span className="num">{events[0].qty} ×</span> {name(events[0].sku)} · {ago(events[0].at)}
        </span>
      )}
    </div>
  )
}

type Shelf = { category: string | null; pieces: number; from: number; piece: CatalogRow | null }

/** One tile per shelf of the shop, drawn from the piece that shelf actually sells: the count and
 *  the "from" price are the catalog's, and so is the drawing. */
function CategoryRail({ shelves, selected, onSelect }: { shelves: Shelf[]; selected: string | null; onSelect: (category: string | null) => void }) {
  const tile = (shelf: Shelf) => (
    <button
      key={shelf.category ?? "everything"}
      type="button"
      aria-pressed={selected === shelf.category}
      aria-label={shelf.category ?? "Everything"}
      onClick={() => onSelect(shelf.category)}
      className={cn(
        "group flex shrink-0 snap-start items-baseline gap-2 border-b-2 py-2 text-left whitespace-nowrap transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
        selected === shelf.category ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      <span className="display text-xl capitalize">{shelf.category ?? "Everything"}</span>
      <span className="num text-xs">
        {shelf.pieces}
        {shelf.from > 0 && ` · from ${price(shelf.from)}`}
      </span>
    </button>
  )
  return (
    <nav aria-label="Shop by category" className="-mx-6 overflow-x-auto border-b border-border px-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <div className="flex snap-x gap-8">{shelves.map(tile)}</div>
    </nav>
  )
}

export function StoreGrid({ initialCategory = null }: { initialCategory?: string | null }) {
  const [rows, setRows] = useState<CatalogRow[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [filter, setFilter] = useState<StoreFilter>({ ...EMPTY_FILTER, category: initialCategory })
  const [width, setWidth] = useState("4.0")
  const [depth, setDepth] = useState("3.5")
  const [height, setHeight] = useState("2.4")
  const [verdicts, setVerdicts] = useState<Record<string, string>>({})
  const [proofs, setProofs] = useState<Record<string, string | null>>({})
  const [progress, setProgress] = useState<{ of: number; total: number } | null>(null)
  const [sweepNote, setSweepNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [fitError, setFitError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)
  const shelf = useShelf()

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

  // A wrong measurement is named, not swapped for a default: the sweep waits for a real room.
  const { room: checked, errors: roomErrors } = useMemo(() => validateRoom({ width, depth, height }), [width, depth, height])
  const roomWidth = checked?.width ?? 4
  const roomDepth = checked?.depth ?? 3.5
  const roomHeight = checked?.height ?? 2.4
  const visible = useMemo(() => sortRows(rows.filter((row) => match(row, filter)), filter, verdicts), [rows, filter, verdicts])
  const cleared = useMemo(() => Object.values(verdicts).filter((verdict) => verdict === "fits" || verdict === "tight").length, [verdicts])

  const shelves = useMemo<Shelf[]>(() => {
    const byCategory = new Map<string, CatalogRow[]>()
    for (const row of rows) byCategory.set(row.category, [...(byCategory.get(row.category) ?? []), row])
    const tiles = [...byCategory.entries()]
      .map(([category, group]) => {
        const cheapest = group.reduce((best, row) => (row.commerce.retail_eur < best.commerce.retail_eur ? row : best), group[0])
        return { category, pieces: group.length, from: cheapest.commerce.retail_eur, piece: cheapest }
      })
      .sort((a, b) => b.pieces - a.pieces || a.category.localeCompare(b.category))
    return [{ category: null, pieces: rows.length, from: 0, piece: null }, ...tiles]
  }, [rows])

  // The bag is measured against the room the shopper was looking at, so the bar tells the bag
  // store what that room is. Lines already proven for another room go stale on their own.
  useEffect(() => {
    trackRoom({ width_m: roomWidth, depth_m: roomDepth, height_m: roomHeight })
  }, [roomWidth, roomDepth, roomHeight])

  /** A sweep for the room on the bar, optionally for a shelf the shopper just chose. The override
   *  is what lets a tile click measure that shelf rather than the one the state still holds. */
  const measure = useCallback(
    async (override: { category?: string | null; priceBand?: string | null } = {}) => {
      const category = "category" in override ? override.category : filter.category
      const priceBand = "priceBand" in override ? override.priceBand : filter.priceBand
      if (!checked) {
        setFitError("Fix the room measurements above before measuring.")
        return
      }
      abort.current?.abort()
      const controller = new AbortController()
      abort.current = controller
      setBusy(true)
      setFitError(null)
      setSweepNote(null)
      setProgress(null)
      try {
        await streamSweep(
          {
            room_width_m: roomWidth,
            room_depth_m: roomDepth,
            room_height_m: roomHeight,
            category,
            price_band: priceBand,
            query: filter.query,
            limit: MEASURE,
          },
          (event: SweepEvent) => {
            if (event.event === "verdict" && event.sku) {
              const sku = event.sku
              setVerdicts((current) => ({ ...current, [sku]: String(event.verdict) }))
              setProofs((current) => ({ ...current, [sku]: event.simulation_id ?? null }))
              setProgress({ of: Number(event.of), total: Number(event.total) })
              return
            }
            if (event.event === "done") setSweepNote(event.note ?? null)
            if (event.event === "error") setFitError(event.detail ?? "The sweep was refused.")
          },
          controller.signal,
        )
      } catch (caught) {
        if (!controller.signal.aborted) setFitError(caught instanceof Error ? caught.message : "The fit sweep did not return.")
      } finally {
        if (abort.current === controller) {
          setBusy(false)
          setProgress(null)
        }
      }
    },
    [checked, roomWidth, roomDepth, roomHeight, filter.category, filter.priceBand, filter.query],
  )

  useEffect(() => () => abort.current?.abort(), [])

  // The shop opens with its shelf already read and its best candidates measured: a verdict on the
  // landing page is the product, not an extra step.
  useEffect(() => {
    if (loaded) void measure()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded])

  function patch(next: Partial<StoreFilter>) {
    setFilter((current) => ({ ...current, ...next }))
  }

  function chooseShelf(category: string | null) {
    const next = filter.category === category ? null : category
    patch({ category: next })
    void measure({ category: next })
  }

  if (loadError) {
    return <p className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{loadError}</p>
  }
  if (!loaded) {
    return (
      <div aria-busy="true" aria-label="Opening the shop" className="grid gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((slot) => (
          <div key={slot} className="space-y-3">
            <div className="aspect-[4/3] animate-pulse rounded-md bg-muted" />
            <div className="h-9 animate-pulse rounded-md bg-muted/70" />
            <div className="h-5 w-2/3 animate-pulse rounded bg-muted/70" />
            <div className="h-24 animate-pulse rounded bg-muted/50" />
          </div>
        ))}
      </div>
    )
  }

  const chip = (label: string, selected: boolean, onClick: () => void) => (
    <Button key={label} type="button" size="sm" variant={selected ? "default" : "outline"} aria-pressed={selected} className="rounded-full" onClick={onClick}>
      {label}
    </Button>
  )

  return (
    <div className="space-y-6">
      <CategoryRail shelves={shelves} selected={filter.category} onSelect={chooseShelf} />

      <div className="sticky top-[3.25rem] z-30 -mx-6 border-b border-border bg-background/95 px-6 py-3 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
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
                {at > 0 && (
                  <span aria-hidden className="text-muted-foreground">
                    ×
                  </span>
                )}
                <Label htmlFor={id} className="sr-only">
                  {labelText} in metres
                </Label>
                <Input
                  id={id}
                  inputMode="decimal"
                  value={value}
                  onChange={(event) => setter(event.target.value)}
                  onFocus={(event) => event.target.select()}
                  disabled={busy}
                  autoComplete="off"
                  aria-invalid={roomErrors[labelText.toLowerCase() as "width" | "depth" | "height"] ? true : undefined}
                  title={roomErrors[labelText.toLowerCase() as "width" | "depth" | "height"]}
                  className="num w-24 bg-background/70 text-center font-semibold aria-invalid:border-destructive aria-invalid:ring-destructive/30"
                />
              </div>
            ))}
            <span className="hidden text-xs text-muted-foreground sm:inline">m · width × depth × height</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <ShelfPulse live={shelf.live} counts={Object.keys(shelf.bySku).length} />
            <Button size="sm" variant="outline" className="rounded-full" onClick={() => shelf.refresh()}>
              <Square className="size-3.5" /> Re-read
            </Button>
            {busy ? (
              <Button
                variant="secondary"
                onClick={() => {
                  abort.current?.abort()
                  setBusy(false)
                  setProgress(null)
                }}
              >
                <StopCircle className="size-4" />
                {progress ? `${progress.of} of ${progress.total} measured` : "Stop"}
              </Button>
            ) : (
              <Button onClick={() => void measure()}>
                <Ruler className="size-4" /> Measure {MEASURE} in my room
              </Button>
            )}
          </div>
        </div>
      </div>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {busy && progress ? (
            <span className="flex items-center gap-1.5 text-primary">
              <Loader2 className="size-3 animate-spin" /> Measuring — a card turns the second its own simulation settles.
            </span>
          ) : sweepNote ? (
            <span>
              <Activity className="mr-1 inline size-3" />
              {cleared} of this sweep cleared the {roomWidth} × {roomDepth} m room. {sweepNote}
            </span>
          ) : (
            <span>Every badge is the geometry engine&rsquo;s own word for this room. Nothing here is guessed.</span>
          )}
          {Object.entries(roomErrors).map(([field, message]) => (
            <span key={field} role="alert" className="text-destructive">
              {field[0].toUpperCase() + field.slice(1)}: {message}
            </span>
          ))}
          {fitError && <span className="text-destructive">{fitError}</span>}
      </p>

      <ShelfActivity events={shelf.events} rows={rows} />

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
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by price tier">
          {chip("Any price", filter.priceBand === null, () => patch({ priceBand: null }))}
          {bands(rows).map((option) => chip(bandLabel(option), filter.priceBand === option, () => patch({ priceBand: filter.priceBand === option ? null : option })))}
        </div>
        <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
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
        <p className="rounded-md border border-dashed p-10 text-center text-sm text-muted-foreground">
          Nothing in the shop matches that. Clear a filter and try again.
        </p>
      ) : (
        <div className="grid gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((row) => (
            <ProductCard
              key={row.sku}
              row={row}
              verdict={verdicts[row.sku]}
              simulationId={proofs[row.sku]}
              stock={shelf.bySku[row.sku]}
              roomWidthM={roomWidth}
              roomDepthM={roomDepth}
              roomHeightM={roomHeight}
            />
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Counts are the shelf&rsquo;s own: {STOCK_LABEL.in_stock.toLowerCase()} means what is on the floor after holds and
        order drafts are taken out.{" "}
        <span className={stockTone("in_stock")}>Green</span> is a piece the engine cleared for the room above,{" "}
        <span className={stockTone("low")}>amber</span> a tight one, and no badge at all is the honest answer — it has
        not been measured.
      </p>
    </div>
  )
}
