/** One bag, as agent-service describes it. Both the store's own tests and the drawer's read these,
 *  because the two are only meaningful if they agree with each other. */

export const line = {
  sku: "SOF-001",
  name: "Linen sofa 160",
  quantity: 1,
  price_eur: 899,
  cost_eur: 503,
  lead_days: 18,
  freight: "pallet",
  volume_m3: 0.4,
  simulation_id: "sim-1",
  verdict: "fits",
  coverage_pct: 10.6,
  walkway_m: { front: 0.7 },
  footprint_m2: 1.408,
  placement_proved: true,
  room: { width_m: 4, depth_m: 3.5, height_m: 2.4 },
  added_at: "2026-10-17T09:00:00+00:00",
}

export function view(over: Record<string, unknown> = {}) {
  return {
    cart_id: "cart-1",
    room: { width_m: 4, depth_m: 3.5, height_m: 2.4 },
    lines: [line],
    items: 1,
    total_eur: 899,
    cost_eur: 503,
    margin_eur: 396,
    volume_m3: 0.4,
    lead_days: 18,
    freight: "pallet",
    unproven: [],
    set: null,
    checkout: { tool: "checkout", ready: true, needs: "the shopper's own confirmation words", how: "ask plainly", refuses: "a line the engine has not cleared" },
    note: "Prices are the catalog's own listed terms.",
    ...over,
  }
}

export const order = {
  id: "ord-1",
  cart_id: "cart-1",
  lines: [line],
  total_eur: 899,
  cost_eur: 503,
  margin_eur: 396,
  lead_days: 18,
  freight: "pallet",
  confirmation: "yes, order it",
  confirmed_through: "typed by the shopper",
  status: "awaiting_merchant",
  created_at: "2026-10-17T09:05:00+00:00",
  proofs: [{ sku: "SOF-001", simulation_id: "sim-1", verdict: "fits", quantity: 1, tightest_walkway_m: 0.7, verify: "/api/v1/simulations/sim-1" }],
  combined: null,
  room: { width_m: 4, depth_m: 3.5, height_m: 2.4 },
  next: "A person at the shop accepts or releases this draft.",
}
