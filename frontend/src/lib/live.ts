/** The two things that make this shop live rather than a picture of one: the shelf it re-reads,
 *  and the sweep it watches. Both read the services, never a fixture — a storefront that ships
 *  with its own numbers cannot be checked against anything. */

"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { fetchStock, fetchStockEvents, type StockEvent, type StockRow } from "@/lib/api"

/** How often the shop re-reads its own shelf. A hold placed from ChatGPT shows up here within this window. */
const SHELF_POLL_MS = 5_000

export type Shelf = {
  bySku: Record<string, StockRow>
  events: StockEvent[]
  live: boolean
  error: string | null
  refresh: () => void
}

export function useShelf(intervalMs = SHELF_POLL_MS): Shelf {
  const [rows, setRows] = useState<StockRow[]>([])
  const [events, setEvents] = useState<StockEvent[]>([])
  const [live, setLive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const alive = useRef(true)

  const read = useCallback(async () => {
    try {
      const [stock, traffic] = await Promise.all([fetchStock(), fetchStockEvents()])
      if (!alive.current) return
      setRows(stock)
      setEvents(traffic)
      setLive(true)
      setError(null)
    } catch (caught) {
      if (!alive.current) return
      setLive(false)
      setError(caught instanceof Error ? caught.message : "catalog-service is not answering.")
    }
  }, [])

  useEffect(() => {
    alive.current = true
    void read()
    const timer = setInterval(() => void read(), intervalMs)
    return () => {
      alive.current = false
      clearInterval(timer)
    }
  }, [read, intervalMs])

  return { bySku: Object.fromEntries(rows.map((row) => [row.sku, row])), events, live, error, refresh: () => void read() }
}

export type SweepEvent = {
  event: "start" | "verdict" | "done" | "error"
  sku?: string
  verdict?: string
  simulation_id?: string | null
  of?: number
  total?: number
  tightest_walkway_m?: number | null
  coverage_pct?: number
  ms?: number
  name?: string
  reason?: string | null
  detail?: string
  fits?: SweepEvent[]
  does_not_fit?: SweepEvent[]
  unproven?: SweepEvent[]
  note?: string
}

export type SweepRoom = {
  room_width_m: number
  room_depth_m: number
  room_height_m: number
  category?: string | null
  price_band?: string | null
  query?: string
  limit?: number
  image_key?: string | null
}

export function sweepUrl(room: SweepRoom): string {
  const params = new URLSearchParams({
    room_width_m: String(room.room_width_m),
    room_depth_m: String(room.room_depth_m),
    room_height_m: String(room.room_height_m),
    limit: String(room.limit ?? 8),
  })
  if (room.category) params.set("category", room.category)
  if (room.price_band) params.set("price_band", room.price_band)
  if (room.query) params.set("query", room.query)
  if (room.image_key) params.set("image_key", room.image_key)
  return `/agent/fit/stream?${params.toString()}`
}

/** Read the sweep as it lands. `onEvent` fires for every verdict the geometry worker settles, so a
 *  card turns green the second its own simulation is done rather than after the slowest one. */
export async function streamSweep(room: SweepRoom, onEvent: (event: SweepEvent) => void, signal?: AbortSignal): Promise<void> {
  const response = await fetch(sweepUrl(room), { headers: { Accept: "text/event-stream" }, cache: "no-store", signal })
  if (!response.ok || !response.body) throw new Error("the fit sweep could not be started.")
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let frame = buffer.indexOf("\n\n")
    while (frame >= 0) {
      const chunk = buffer.slice(0, frame)
      buffer = buffer.slice(frame + 2)
      const data = chunk
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("")
      if (data) onEvent(JSON.parse(data) as SweepEvent)
      frame = buffer.indexOf("\n\n")
    }
  }
}
