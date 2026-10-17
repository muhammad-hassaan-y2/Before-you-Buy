/** The shopper's bag, as agent-service holds it. The browser keeps one id and nothing else: the
 *  bag is the service's, `add_to_cart` mints it, and every read cites it. So a bag here is a
 *  handle plus the room it belongs to - the prices, verdicts and totals come from the tools.
 *
 *  A restart drops the in-process bag, and that is not an error worth showing a shopper: an
 *  unknown id reads as an empty bag, and the next add starts a fresh one. */

import { useSyncExternalStore } from "react"

import { callTool } from "./agent"

export type BagRoom = { width_m: number; depth_m: number; height_m: number }

export const DEFAULT_ROOM: BagRoom = { width_m: 4, depth_m: 3.5, height_m: 2.4 }

export type BagLine = {
  sku: string
  name: string
  quantity: number
  price_eur: number
  cost_eur: number
  lead_days: number
  freight: string
  volume_m3: number
  simulation_id: string | null
  verdict: string | null
  coverage_pct: number
  walkway_m: Record<string, number>
  footprint_m2: number
  placement_proved: boolean
  room: BagRoom | null
  added_at: string
}

/** The set verdict: the footprints and walkways of the bag added up over one room. */
export type BagSet = {
  verdict: string
  footprint_m2: number
  usable_area_m2: number
  coverage_pct: number
  tightest_walkway_m: number | null
  conflicts: string[]
  footprint_estimated_from_listing: string[]
  note: string
}

export type Bag = {
  cart_id: string
  room: BagRoom
  lines: BagLine[]
  items: number
  total_eur: number
  cost_eur: number
  margin_eur: number
  volume_m3: number
  lead_days: number
  freight: string
  unproven: string[]
  set: BagSet | null
  checkout: { tool: string; ready: boolean; needs: string; how: string; refuses: string }
  note: string
}

/** What one measurement round spent on the bag. Only lines without a proof for the current room
 *  are re-measured, so this is often empty even after the button is pressed. */
export type Measured = { sku: string; name: string; verdict: string | null; quantity: number; tightest_walkway_m: number | null; ms: number; verify: string | null }

export type OrderProof = { sku: string; simulation_id: string | null; verdict: string | null; quantity: number; tightest_walkway_m: number | null; verify: string | null }

export type Order = {
  id: string
  cart_id: string
  lines: BagLine[]
  total_eur: number
  cost_eur: number
  margin_eur: number
  lead_days: number
  freight: string
  confirmation: string
  confirmed_through: string
  status: string
  created_at: string
  proofs: OrderProof[]
  combined: BagSet | null
  room: BagRoom | null
  next?: string
}

export type BagState = {
  bag: Bag | null
  room: BagRoom
  open: boolean
  busy: boolean
  error: string | null
  order: Order | null
}

const STORAGE = "byb.bag"

function readStored(): { cart_id: string | null; room: BagRoom } {
  const empty = { cart_id: null, room: DEFAULT_ROOM }
  if (typeof window === "undefined") return empty
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE) ?? "{}") as Partial<{ cart_id: string; room: BagRoom }>
    return { cart_id: typeof stored.cart_id === "string" ? stored.cart_id : null, room: { ...DEFAULT_ROOM, ...(stored.room ?? {}) } }
  } catch {
    // A private tab that will not keep the id is not worth breaking the page over.
    return empty
  }
}

function store(patch: Partial<{ cart_id: string | null; room: BagRoom }>) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(STORAGE, JSON.stringify({ ...readStored(), ...patch }))
  } catch {
    // Same: the bag still lives in the service for this visit.
  }
}

export type ActionResult = { ok: boolean; bag: Bag | null; order: Order | null; error: string | null }

let state: BagState = { bag: null, room: readStored().room, open: false, busy: false, error: null, order: null }
const listeners = new Set<() => void>()

function set(patch: Partial<BagState>) {
  state = { ...state, ...patch }
  for (const listener of listeners) listener()
}

function cartId(): string | null {
  return readStored().cart_id
}

/** A bag the service no longer has reads as an empty one, so the id goes and the shopper sees a
 *  shelf rather than a stack trace. */
function lostBag(message: string): boolean {
  return /unknown cart|is not in this process|is not in cart/.test(message)
}

function settle(caught: unknown): ActionResult {
  const message = caught instanceof Error ? caught.message : "agent-service did not answer."
  if (lostBag(message)) {
    store({ cart_id: null })
    set({ bag: null, error: null })
    return { ok: false, bag: null, order: null, error: null }
  }
  set({ error: message })
  return { ok: false, bag: state.bag, order: state.order, error: message }
}

function succeeded(bag: Bag | null): ActionResult {
  set({ bag, error: null })
  return { ok: true, bag, order: state.order, error: null }
}

async function run(work: () => Promise<Bag>): Promise<ActionResult> {
  set({ busy: true, error: null })
  try {
    const bag = await work()
    store({ cart_id: bag.cart_id })
    return succeeded(bag)
  } catch (caught) {
    return settle(caught)
  } finally {
    set({ busy: false })
  }
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function snapshot(): BagState {
  return state
}

export function useBag(): BagState {
  return useSyncExternalStore(subscribe, snapshot, snapshot)
}

/** The room the shopper is shopping for. The store bar and the listing both push it here, so a
 *  bag added from one page is measured against the same room in the next. */
export function trackRoom(room: BagRoom): void {
  store({ room })
  set({ room })
}

export function bagRoom(): BagRoom {
  return state.bag?.room ?? state.room
}

export function openBag(): void {
  set({ open: true, error: null })
  void refreshBag()
}

export function closeBag(): void {
  set({ open: false })
}

export async function refreshBag(): Promise<ActionResult> {
  const id = cartId()
  if (!id) {
    set({ bag: null })
    return { ok: true, bag: null, order: state.order, error: null }
  }
  return run(() => callTool<Bag>("view_cart", { cart_id: id }))
}

export async function addToBag(sku: string, options: { simulationId?: string | null; quantity?: number; room?: BagRoom } = {}): Promise<ActionResult> {
  const room = options.room ?? state.room
  if (options.room) trackRoom(options.room)
  const result = await run(() =>
    callTool<Bag>("add_to_cart", {
      sku,
      cart_id: cartId(),
      quantity: options.quantity ?? 1,
      simulation_id: options.simulationId ?? null,
      room_width_m: room.width_m,
      room_depth_m: room.depth_m,
      room_height_m: room.height_m,
    }),
  )
  if (result.ok) set({ open: true })
  return result
}

export async function setQuantity(sku: string, quantity: number): Promise<ActionResult> {
  const id = cartId()
  if (!id) return { ok: false, bag: null, order: null, error: "the bag is empty" }
  return run(() =>
    callTool<Bag>("add_to_cart", {
      sku,
      cart_id: id,
      quantity: Math.max(1, Math.floor(quantity)),
      room_width_m: state.room.width_m,
      room_depth_m: state.room.depth_m,
      room_height_m: state.room.height_m,
    }),
  )
}

export async function removeFromBag(sku: string): Promise<ActionResult> {
  const id = cartId()
  if (!id) return { ok: false, bag: null, order: null, error: "the bag is empty" }
  return run(() => callTool<Bag>("remove_from_cart", { cart_id: id, sku }))
}

/** Put the bag through the geometry engine. Lines already cleared for this room come back
 *  untouched, so pressing this twice costs nothing the second time. */
export async function measureBag(): Promise<ActionResult> {
  const id = cartId()
  if (!id) return { ok: false, bag: null, order: null, error: "the bag is empty" }
  const room = state.room
  return run(() =>
    callTool<Bag>("measure_cart", {
      cart_id: id,
      room_width_m: room.width_m,
      room_depth_m: room.depth_m,
      room_height_m: room.height_m,
    }),
  )
}

/** Checkout takes the shopper's own words, so the UI passes what they typed and nothing else. */
export async function placeOrder(confirmation: string): Promise<ActionResult & { order: Order | null }> {
  const id = cartId()
  if (!id) return { ok: false, bag: null, order: null, error: "the bag is empty" }
  set({ busy: true, error: null })
  try {
    const order = await callTool<Order>("checkout", { cart_id: id, confirmation })
    store({ cart_id: null })
    set({ order, bag: null, error: null })
    return { ok: true, bag: null, order, error: null }
  } catch (caught) {
    const failed = settle(caught)
    return { ...failed, order: null }
  } finally {
    set({ busy: false })
  }
}

export function dismissOrder(): void {
  set({ order: null })
  void refreshBag()
}

/** The words agent-service reads as a shopper's own yes. Mirrors CONFIRMATIONS in tools.py: the
 *  gate lives in the service and cannot be satisfied from here, so this only keeps the shop from
 *  offering a click it knows would come back refused. */
export const CONFIRMATIONS = [
  "yes",
  "y",
  "yeah",
  "yep",
  "ok",
  "okay",
  "confirm",
  "confirmed",
  "i confirm",
  "hold it",
  "hold this",
  "please hold it",
  "approved",
  "go ahead",
]

export function soundsConfirmed(words: string): boolean {
  const said = words.trim().toLowerCase()
  if (!said) return false
  return CONFIRMATIONS.includes(said) || CONFIRMATIONS.some((token) => new RegExp(`\\b${token}\\b`).test(said))
}
