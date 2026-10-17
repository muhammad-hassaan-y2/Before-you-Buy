import { describe, expect, it } from "vitest"

import type { CatalogRow } from "@/lib/api"
import { bands, categories, EMPTY_FILTER, match, price, sortRows, verdictLabel, verdictVariant } from "@/lib/store"

function row(overrides: Partial<CatalogRow> = {}): CatalogRow {
  return {
    sku: "BYB-KURA-3S",
    name: "KURA three-seat sofa",
    brand: "KURA",
    category: "sofa",
    material: "linen",
    price_band: "$$",
    geometry: { width_cm: 200, depth_cm: 90, height_cm: 84, clearance_cm: 10 },
    commerce: {
      currency: "EUR",
      retail_eur: 919,
      cost_eur: 515,
      margin_eur: 404,
      margin_pct: 44,
      volume_m3: 1.512,
      supplier: { name: "Porto Frame Works", region: "PT" },
      lead_days: 18,
      freight: "pallet",
      product_url: "https://shop.example.com/p/kura/",
      basis: "derived from the SKU's price band, category and box size",
    },
    ...overrides,
  }
}

const sofa = row()
const bookcase = row({
  sku: "BYB-BILLY-80",
  name: "BILLY bookcase 80 cm",
  brand: "BILLY",
  category: "bookcase",
  material: "oak veneer",
  price_band: "$",
  geometry: { width_cm: 80, depth_cm: 28, height_cm: 202, clearance_cm: 5 },
  commerce: { ...sofa.commerce, retail_eur: 399, cost_eur: 176, margin_eur: 223, margin_pct: 55.9, volume_m3: 0.4525, lead_days: 15, freight: "parcel" },
})

describe("store filters", () => {
  it("needs every word to appear somewhere in the listing", () => {
    expect(match(sofa, { ...EMPTY_FILTER, query: "linen sofa" })).toBe(true)
    expect(match(sofa, { ...EMPTY_FILTER, query: "linen oak" })).toBe(false)
    expect(match(sofa, EMPTY_FILTER)).toBe(true)
  })

  it("narrows by category, band and freight", () => {
    expect(match(bookcase, { ...EMPTY_FILTER, category: "bookcase" })).toBe(true)
    expect(match(bookcase, { ...EMPTY_FILTER, priceBand: "$$" })).toBe(false)
    expect(match(bookcase, { ...EMPTY_FILTER, freight: "parcel" })).toBe(true)
    expect(match(sofa, { ...EMPTY_FILTER, freight: "parcel" })).toBe(false)
  })

  it("lists the choices a shopper can filter by, once each", () => {
    expect(categories([sofa, bookcase, sofa])).toEqual(["bookcase", "sofa"])
    expect(bands([sofa, bookcase])).toEqual(["$", "$$"])
  })
})

describe("store sorting", () => {
  const measured = { "BYB-BILLY-80": "fits", "BYB-OTHER": "too_large" }

  it("puts a measured fit above an unmeasured piece, whatever its price", () => {
    const cheap = row({ sku: "BYB-CHEAP", commerce: { ...sofa.commerce, retail_eur: 10 } })
    const listed = sortRows([cheap, bookcase], { ...EMPTY_FILTER, sort: "fit" }, measured)
    expect(listed.map((item) => item.sku)).toEqual(["BYB-BILLY-80", "BYB-CHEAP"])
  })

  it("keeps a fit ahead of a piece that was measured and refused", () => {
    const blocked = row({ sku: "BYB-OTHER" })
    const listed = sortRows([blocked, bookcase], { ...EMPTY_FILTER, sort: "fit" }, measured)
    expect(listed.map((item) => item.sku)).toEqual(["BYB-BILLY-80", "BYB-OTHER"])
  })

  it("reads price, margin, lead time and box size off the terms", () => {
    const key = (sort: "price" | "margin" | "lead" | "size") =>
      sortRows([sofa, bookcase], { ...EMPTY_FILTER, sort }, {}).map((item) => item.sku)
    expect(key("price")).toEqual(["BYB-BILLY-80", "BYB-KURA-3S"])
    expect(key("margin")).toEqual(["BYB-BILLY-80", "BYB-KURA-3S"])
    expect(key("lead")).toEqual(["BYB-BILLY-80", "BYB-KURA-3S"])
    expect(key("size")).toEqual(["BYB-KURA-3S", "BYB-BILLY-80"])
  })
})

describe("store copy", () => {
  it("quotes euros the way the shelf does", () => {
    expect(price(919)).toBe("€919")
  })

  it("names a verdict instead of dressing it up as stock", () => {
    expect(verdictLabel("fits")).toBe("Fits")
    expect(verdictLabel("tight")).toBe("Tight fit")
    expect(verdictLabel(undefined)).toBe("Not measured")
    expect(verdictVariant("fits")).toBe("success")
    expect(verdictVariant("tight")).toBe("warning")
    expect(verdictVariant("too_large")).toBe("destructive")
    expect(verdictVariant("pending")).toBe("outline")
  })
})
