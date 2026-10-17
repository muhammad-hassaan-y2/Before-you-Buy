/** The shop's own reading of a catalog row. Everything here is arithmetic over what the
 *  gateway already sent — the storefront never holds a price the service did not compute. */

import type { CatalogRow, StockRow } from "@/lib/api"

export type StoreSort = "fit" | "price" | "margin" | "lead" | "size"

export type StoreFilter = {
  query: string
  category: string | null
  priceBand: string | null
  freight: string | null
  sort: StoreSort
}

export const EMPTY_FILTER: StoreFilter = { query: "", category: null, priceBand: null, freight: null, sort: "fit" }

/** Verdicts the geometry engine passes. Mirrors PASS_VERDICTS in agent-service, which is the
 *  set that can be recommended, so a card never shows green for something the agent would refuse. */
export const PASS_VERDICTS = ["fits", "tight"]
export const FAIL_VERDICTS = ["too_large", "blocked"]

const eur = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 })

export function price(value: number): string {
  return eur.format(value)
}

export function match(row: CatalogRow, filter: StoreFilter): boolean {
  if (filter.category && row.category !== filter.category) return false
  if (filter.priceBand && row.price_band !== filter.priceBand) return false
  if (filter.freight && row.commerce.freight !== filter.freight) return false
  const words = filter.query.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return true
  const haystack = [row.name, row.brand, row.category, row.material ?? "", row.sku, row.commerce.supplier.name]
    .join(" ")
    .toLowerCase()
  return words.every((word) => haystack.includes(word))
}

export function sortRows(rows: CatalogRow[], filter: StoreFilter, verdicts: Record<string, string>): CatalogRow[] {
  const listed = [...rows]
  if (filter.sort === "fit") {
    // Measured pieces first, and inside them the shop's own walkway verdict, then price.
    return listed.sort((a, b) => rank(verdicts[a.sku]) - rank(verdicts[b.sku]) || a.commerce.retail_eur - b.commerce.retail_eur)
  }
  const key: Record<Exclude<StoreSort, "fit">, (row: CatalogRow) => number> = {
    price: (row) => row.commerce.retail_eur,
    margin: (row) => -row.commerce.margin_pct,
    lead: (row) => row.commerce.lead_days,
    size: (row) => -row.commerce.volume_m3,
  }
  const read = key[filter.sort]
  return listed.sort((a, b) => read(a) - read(b) || a.name.localeCompare(b.name))
}

function rank(verdict: string | undefined): number {
  if (!verdict) return 3
  if (PASS_VERDICTS.includes(verdict)) return 0
  return FAIL_VERDICTS.includes(verdict) ? 2 : 1
}

export function categories(rows: CatalogRow[]): string[] {
  return [...new Set(rows.map((row) => row.category))].sort()
}

export function bands(rows: CatalogRow[]): string[] {
  return [...new Set(rows.map((row) => row.price_band).filter((band) => !!band))].sort() as string[]
}

/** catalog-service prices a SKU off its band anchor (€350 / €750 / €1,500) scaled by box size, so
 *  a band is a tier and not a ceiling. The chips say tier, never a range that would be a lie. */
export function bandLabel(band: string): string {
  return { $: "Budget", $$: "Midrange", $$$: "Premium" }[band] ?? band
}

/** The words a card puts next to a verdict, so the badge says what was measured rather than
 *  looking like a stock indicator. */
export function verdictLabel(verdict: string | undefined): string {
  if (!verdict) return "Not measured"
  return (
    {
      fits: "Fits",
      tight: "Tight fit",
      too_large: "Too large",
      blocked: "No clear spot",
    }[verdict] ?? verdict
  )
}

export function verdictVariant(verdict: string | undefined): "success" | "warning" | "destructive" | "outline" {
  if (!verdict) return "outline"
  if (PASS_VERDICTS.includes(verdict)) return verdict === "tight" ? "warning" : "success"
  if (FAIL_VERDICTS.includes(verdict)) return "destructive"
  return "outline"
}

/** How the shop talks about its own shelf. The count comes from catalog-service; these are only
 *  the words around it, kept in one place so a card and a listing page cannot say different things. */
export const STOCK_LABEL: Record<StockRow["state"], string> = {
  in_stock: "In stock",
  low: "Low stock",
  backorder: "Out of stock",
  made_to_order: "Made to order",
}

export function stockTone(state: StockRow["state"] | undefined): string {
  if (state === "in_stock") return "text-success"
  if (state === "low") return "text-warning"
  if (state === "backorder") return "text-destructive"
  return "text-muted-foreground"
}

export function stockLine(row: StockRow | undefined): string {
  if (!row) return "Count not loaded"
  if (row.state === "made_to_order") return `Cut after your order · ${row.lead_days} days`
  if (row.available === 0) return `Next lot on the floor in ${row.next_lot_in_days} days`
  if (row.state === "low") return `${row.available} left · ${row.reserved} held`
  return `${row.available} of ${row.on_hand} on the floor`
}

/** "3 minutes ago", from the shop's own event log, so the activity rail reads as traffic and not as copy. */
export function ago(iso: string, now = Date.now()): string {
  const seconds = Math.max(Math.round((now - new Date(iso).getTime()) / 1000), 0)
  if (seconds < 45) return "just now"
  if (seconds < 3_600) return `${Math.round(seconds / 60)} min ago`
  if (seconds < 86_400) return `${Math.round(seconds / 3_600)} h ago`
  return `${Math.round(seconds / 86_400)} d ago`
}
