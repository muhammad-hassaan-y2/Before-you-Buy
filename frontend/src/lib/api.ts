/** Typed client for the api-gateway. Requests go to /api/v1/*, which next.config.ts
 *  proxies to the FastAPI gateway, so no backend origin is baked into the browser bundle. */

const BASE = "/api/v1"

export type ProductPart = {
  label: string
  size_cm: [number, number, number]
  offset_cm: [number, number, number]
  tone: string
}

export type ProductGeometry = {
  width_cm: number
  depth_cm: number
  height_cm: number
  clearance_cm: number
}

export type ProductProfile = {
  name: string
  brand?: string | null
  category: string
  material?: string | null
  price_band?: string | null
  geometry: ProductGeometry
  confidence: number
  summary: string
  source: string
  parts?: ProductPart[]
}

export type CatalogCandidate = {
  sku: string
  name: string
  brand: string
  category: string
  material?: string | null
  price_band?: string | null
  geometry: ProductGeometry
  parts?: ProductPart[]
  score: number
  source: string
}

export type SimulationStage =
  | "pending"
  | "cataloguing"
  | "enriching"
  | "measuring"
  | "scanning"
  | "fitting"
  | "rendering"
  | "completed"
  | "failed"

export type FitPlacement = {
  label: string
  ring: [number, number][]
  area_m2: number
  footprint_m2: number
  fits: boolean
}

export type FitReport = {
  room_area_m2: number
  usable_area_m2: number
  placements: FitPlacement[]
  conflicts: string[]
  coverage_pct: number
  verdict: "fits" | "tight" | "too_large" | "blocked"
}

export type Simulation = {
  id: string
  status: SimulationStage
  product_link?: string | null
  image_key?: string | null
  created_at: string
  updated_at: string
  error?: string | null
  room_width_m: number
  room_depth_m: number
  room_height_m: number
  shopper_notes?: string | null
  product_profile?: ProductProfile | null
  catalog_candidate?: CatalogCandidate | null
  fit_report?: FitReport | null
}

export type SimulationInput = {
  link?: string
  file?: File | null
  roomWidthM: number
  roomDepthM: number
  roomHeightM: number
  notes?: string
}

export class ApiError extends Error {}

async function message(response: Response): Promise<string> {
  try {
    const body = await response.json()
    const detail = body?.detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) {
      return detail.map((issue) => `${(issue.loc ?? []).slice(1).join(".")}: ${issue.msg}`).join("; ")
    }
    return response.statusText
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

export async function createSimulation(input: SimulationInput): Promise<{ id: string; status: string }> {
  const form = new FormData()
  if (input.link) form.set("link", input.link)
  if (input.file) form.set("file", input.file)
  form.set("room_width_m", String(input.roomWidthM))
  form.set("room_depth_m", String(input.roomDepthM))
  form.set("room_height_m", String(input.roomHeightM))
  if (input.notes) form.set("shopper_notes", input.notes)

  const response = await fetch(`${BASE}/simulations`, { method: "POST", body: form })
  if (!response.ok) throw new ApiError(await message(response))
  return response.json()
}

export async function fetchSimulation(id: string): Promise<Simulation> {
  const response = await fetch(`${BASE}/simulations/${id}`, { cache: "no-store" })
  if (!response.ok) throw new ApiError(await message(response))
  return response.json()
}

export type CatalogRow = {
  sku: string
  name: string
  brand: string
  category: string
  material?: string | null
  price_band?: string | null
  geometry: ProductGeometry
}

/** The gateway proxies catalog-service, so the browser still talks to one origin. */
export async function fetchCatalog(): Promise<CatalogRow[]> {
  const response = await fetch(`${BASE}/catalog`, { cache: "no-store" })
  if (!response.ok) throw new ApiError(await message(response))
  return response.json()
}

/** Poll until the workers settle. Returns the last snapshot on timeout. */
export async function pollSimulation(
  id: string,
  onUpdate: (simulation: Simulation) => void,
  { intervalMs = 1200, attempts = 40, signal }: { intervalMs?: number; attempts?: number; signal?: AbortSignal } = {},
): Promise<Simulation | null> {
  let last: Simulation | null = null
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (signal?.aborted) return last
    last = await fetchSimulation(id)
    onUpdate(last)
    if (last.status === "completed" || last.status === "failed") return last
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
  return last
}
