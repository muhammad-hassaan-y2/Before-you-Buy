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

export async function startJourney(input: { brief: string; roomWidthM?: number; roomDepthM?: number; roomHeightM?: number }): Promise<{ run_id: string; status: string; poll: string }> {
  const body = JSON.stringify({
    brief: input.brief,
    room_width_m: input.roomWidthM ?? null,
    room_depth_m: input.roomDepthM ?? null,
    room_height_m: input.roomHeightM ?? null,
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
