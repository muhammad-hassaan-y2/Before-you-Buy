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

export type DimensionReliability = "verified" | "extracted" | "estimated"

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
  provider?: string | null
  model?: string | null
  /** Per-axis evidence for the numbers geometry-service placed the box with. */
  dimension_reliability?: Record<string, DimensionReliability>
  measurement_basis?: string | null
  parts?: ProductPart[]
}

/** `ProductProfile.source` straight from the contract, keyed for a badge. */
export const PRODUCT_SOURCE: Record<string, string> = {
  amd_token_factory: "AMD Token Factory",
  catalog: "Catalog SKU",
  heuristic: "Category heuristics",
  // Rows written before the provider was named.
  vllm: "vLLM",
}

const AXES: Record<string, string> = {
  width_cm: "width",
  depth_cm: "depth",
  height_cm: "height",
}

/** Footprint axes the engine placed the box with a category guess for, not a read number. */
export function estimatedAxes(profile: ProductProfile): string[] {
  const reliability = profile.dimension_reliability ?? {}
  return Object.keys(AXES)
    .filter((axis) => reliability[axis] === "estimated")
    .map((axis) => AXES[axis])
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

export type Obstacle = {
  label: string
  /** Polygon ring in metres, room-local. */
  ring: [number, number][]
  height_m: number
  source: string
}

export type RoomScan = {
  width_m: number
  depth_m: number
  height_m: number
  obstacles: Obstacle[]
  /** False when the photo could not be read and the shopper's own numbers stood. */
  measured: boolean
  method: "declared" | "photo" | "photo-ignored"
  confidence: number
}

/** Which room the fit was measured against, told the way the shopper would read it. */
export const ROOM_SCAN_LABEL: Record<string, string> = {
  photo: "Room measured from your photo",
  "photo-ignored": "Photo unreadable — using your numbers",
  declared: "Using your numbers",
}

export type FitPlacement = {
  label: string
  ring: [number, number][]
  area_m2: number
  footprint_m2: number
  fits: boolean
  centre_x_m: number
  centre_y_m: number
  rotation_deg: number
  /** Gap in metres on each face: left, right, front, back. */
  walkway_m: Record<string, number>
}

/** Everything geometry-service says about one piece in one room. The verdict is the engine's;
 *  the delivery-path fields are what turns it from "fits on the plan" into "you can get it in
 *  and still walk around it". */
export type FitReport = {
  room_area_m2: number
  usable_area_m2: number
  placements: FitPlacement[]
  conflicts: string[]
  coverage_pct: number
  verdict: "fits" | "tight" | "too_large" | "blocked"
  obstacles: Obstacle[]
  /** Quarter-circle the room door sweeps. */
  door_swing_m: number
  /** Can the box get through the doorway at all: pass | tight | blocked | unknown. */
  door_pass: "pass" | "tight" | "blocked" | "unknown"
  /** False when the entrance is cut off at the required clearance. */
  walkway_connected: boolean
  /** Floor areas the piece seals off from the door. */
  isolated_pockets: number
  /** Passes on these numbers, fails inside the survey tolerance. */
  fragile: boolean
  tolerance_cm: number
  suggestions: string[]
}

/** What scene-service publishes for the browser engine: metres, right-handed y-up, room
 *  origin in the corner beside the door hinge. Parts stay in centimetres. */
export type ScenePlacement = {
  label: string
  fits: boolean
  position_m: [number, number, number]
  rotation_deg: number
  walkway_m: Record<string, number>
}

export type SceneCamera = {
  label: string
  position_m: [number, number, number]
  target_m: [number, number, number]
  fov_deg: number
}

export type SceneSpec = {
  version: string
  room_width_m: number
  room_depth_m: number
  room_height_m: number
  walls: Obstacle[]
  door_swing_m: number
  product_name: string
  product_category: string
  parts: ProductPart[]
  geometry: ProductGeometry
  clearance_m: number
  placements: ScenePlacement[]
  cameras: SceneCamera[]
  verdict: FitReport["verdict"]
  coverage_pct: number
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
  room_scan?: RoomScan | null
  fit_report?: FitReport | null
  scene?: SceneSpec | null
  has_model?: boolean
}

export type SimulationInput = {
  link?: string
  file?: File | null
  /** A room photo this gateway already stored, so the same room is measured once per piece. */
  imageKey?: string
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
  if (input.imageKey) form.set("image_key", input.imageKey)
  form.set("room_width_m", String(input.roomWidthM))
  form.set("room_depth_m", String(input.roomDepthM))
  form.set("room_height_m", String(input.roomHeightM))
  if (input.notes) form.set("shopper_notes", input.notes)

  const response = await fetch(`${BASE}/simulations`, { method: "POST", body: form })
  if (!response.ok) throw new ApiError(await message(response))
  return response.json()
}

/** Store a room photo on its own and return the key a brief or an agent call can point at. */
export async function uploadRoomPhoto(file: File): Promise<string> {
  const form = new FormData()
  form.set("file", file)
  const response = await fetch(`${BASE}/uploads`, { method: "POST", body: form })
  if (!response.ok) throw new ApiError(await message(response))
  return (await response.json()).image_key
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
