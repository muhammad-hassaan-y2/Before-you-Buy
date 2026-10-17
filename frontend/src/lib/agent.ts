/** Typed client for agent-service. Requests go to /agent/*, which next.config.ts proxies to
 *  the FastAPI agent service, so the Evolus workspace key never reaches the browser. */

const BASE = "/agent"

export type ShopperBrief = {
  raw: string
  category: string | null
  price_band: string | null
  budget_eur: number | null
  room_width_m: number | null
  room_depth_m: number | null
  room_height_m: number | null
  must_haves: string[]
  confidence: number
  source: string
}

export type AgentStep = {
  index: number
  kind: string
  status: string
  detail: string
  tool: string | null
  group: string | null
  iteration: number
  ms: number
  output: Record<string, unknown> | null
}

export type FitAttempt = {
  sku: string
  name: string
  price_band: string | null
  score: number
  simulation_id: string | null
  status: string
  verdict: string | null
  coverage_pct: number
  walkway_m: Record<string, number>
  reason: string | null
}

export type AgentDecision = {
  action: string
  sku: string | null
  simulation_id: string | null
  confidence: number
  reason: string
  evidence: Record<string, unknown> | null
}

export type AgentRun = {
  id: string
  status: "running" | "done" | "awaiting_human" | "failed"
  brief: ShopperBrief | null
  steps: AgentStep[]
  attempts: FitAttempt[]
  decision: AgentDecision | null
  reply: string | null
  evolus_execution_id: string | null
  conversation_id: string | null
  error: string | null
}

export type ToolSpec = { name: string; description: string }

/** A hold the agent took on a shopper's own yes. Not an order: nothing is charged and nothing
 *  ships, and the words the confirmation came in with are on the record. */
export type Reservation = {
  id: string
  simulation_id: string
  sku: string | null
  name: string | null
  verdict: string | null
  confirmation: string
  status: string
  created_at: string
}

export type ReturnsAssumptions = {
  ordersPerMonth?: number
  priceBand?: string | null
  priceEur?: number | null
  returnRate?: number | null
  fitShare?: number | null
  prevention?: number | null
}

/** Arithmetic over stated assumptions, not a forecast of this shop's month. */
export type ReturnsEstimate = {
  orders_per_month: number
  returns_per_month: number
  fit_driven_returns_per_month: number
  returns_prevented_per_month: number
  handling_saved_eur_per_month: number
  revenue_kept_eur_per_month: number
  per_simulation_value_eur: number
  assumptions: {
    return_rate: number
    fit_driven_share_of_returns: number
    handling_cost_eur_per_return: number
    average_order_value_eur: number
    share_of_fit_returns_prevented: number
    note: string
  }
}

export class AgentError extends Error {}

async function message(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return typeof body?.detail === "string" ? body.detail : response.statusText
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${BASE}${path}`, { cache: "no-store", ...init })
  if (!response.ok) throw new AgentError(await message(response))
  return response
}

export async function startJourney(input: {
  brief: string
  roomWidthM?: number
  roomDepthM?: number
  roomHeightM?: number
  imageKey?: string
}): Promise<{ run_id: string; status: string; poll: string }> {
  const body = JSON.stringify({
    brief: input.brief,
    room_width_m: input.roomWidthM ?? null,
    room_depth_m: input.roomDepthM ?? null,
    room_height_m: input.roomHeightM ?? null,
    image_key: input.imageKey ?? null,
  })
  return (await request("/brief", { method: "POST", headers: { "Content-Type": "application/json" }, body })).json()
}

export async function fetchRun(runId: string): Promise<AgentRun> {
  return (await request(`/runs/${runId}`)).json()
}

export async function listRuns(limit = 10): Promise<{ id: string; status: string }[]> {
  return (await request(`/runs?limit=${limit}`)).json()
}

export async function fetchTools(): Promise<ToolSpec[]> {
  const body: { tools: ToolSpec[] } = await (await request("/tools")).json()
  return body.tools
}

/** The holds waiting on a person at the shop, newest first. */
export async function fetchReservations(limit = 20): Promise<Reservation[]> {
  return (await request(`/reservations?limit=${limit}`)).json()
}

/** One capability, called the way an Evolus workflow step calls it. The gateway wraps the
 *  result in `{tool, result}`, so that is what unwraps here. */
export async function callTool<T>(name: string, payload: Record<string, unknown> = {}): Promise<T> {
  const body: { tool: string; result: T } = await (
    await request(`/tools/${name}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
  ).json()
  return body.result
}

export async function returnsEstimate(assumptions: ReturnsAssumptions = {}): Promise<ReturnsEstimate> {
  return callTool<ReturnsEstimate>("returns_estimate", {
    orders_per_month: assumptions.ordersPerMonth ?? 1000,
    price_band: assumptions.priceBand ?? null,
    price_eur: assumptions.priceEur ?? null,
    return_rate: assumptions.returnRate ?? null,
    fit_share: assumptions.fitShare ?? null,
    prevention: assumptions.prevention ?? null,
  })
}

export type ChatReply = { answer: string; answered_by: string; conversation_id?: string }

export async function chat(messages: { role: string; content: string }[], conversationId?: string): Promise<ChatReply> {
  const response = await request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(conversationId ? { "X-Conversation-Id": conversationId } : {}) },
    body: JSON.stringify({ messages, conversation_id: conversationId ?? null }),
  })
  const reply: ChatReply = await response.json()
  return reply
}

/** Poll a journey until it settles. Returns the last snapshot on timeout or abort. */
export async function pollRun(
  runId: string,
  onUpdate: (run: AgentRun) => void,
  { intervalMs = 1000, attempts = 90, signal }: { intervalMs?: number; attempts?: number; signal?: AbortSignal } = {},
): Promise<AgentRun | null> {
  let last: AgentRun | null = null
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (signal?.aborted) return last
    last = await fetchRun(runId)
    onUpdate(last)
    if (last.status !== "running") return last
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
  return last
}

/** What a journey actually spent. Read off the trace, never estimated: the geometry worker did
 *  the measuring, so the only token cost is the steps this set of tools had to ask a model about. */
export type RunCost = {
  /** Wall-clock across the steps, in ms. Parallel fan-out overlaps, so this is the trace's own total. */
  total_ms: number
  /** Pieces the geometry worker actually measured. */
  fits: number
  /** Steps that went to Evolus or the AMD-hosted model rather than to a service. */
  model_calls: number
  /** Loop passes the search ran: 1, or 2 when the band had to widen. */
  passes: number
  slowest: { label: string; ms: number } | null
}

/** Tools that cost nothing but a service hop. Anything else on a step is a model call. */
const DETERMINISTIC = new Set([
  "heuristics",
  "policy",
  "template",
  "geometry-service",
  "GET /api/v1/catalog",
  "POST /api/v1/simulations",
  "agent-service /agent/brief",
])

export function runCost(run: AgentRun): RunCost {
  const counted = run.steps.filter((step) => step.status !== "skipped")
  const slowest = [...counted].sort((a, b) => b.ms - a.ms)[0]
  return {
    total_ms: counted.reduce((total, step) => total + step.ms, 0),
    fits: run.steps.filter((step) => step.kind === "fit").length,
    model_calls: counted.filter((step) => step.tool && !DETERMINISTIC.has(step.tool)).length,
    passes: run.steps.reduce((pass, step) => Math.max(pass, step.iteration), 0),
    slowest: slowest && slowest.ms > 0 ? { label: stepLabel(slowest), ms: slowest.ms } : null,
  }
}

function stepLabel(step: AgentStep): string {
  if (step.kind === "fit") return step.detail.split(" ")[0] || step.kind
  return step.kind
}
