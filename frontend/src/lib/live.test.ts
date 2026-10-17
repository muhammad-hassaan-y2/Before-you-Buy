import { describe, expect, it, vi } from "vitest"

import { streamSweep, sweepUrl } from "@/lib/live"

/** The sweep is only live if the reader turns the frames back into events as they arrive, so the
 *  parser is tested with a body that hands over bytes in whatever chunks the network felt like. */
function body(chunks: string[]) {
  let at = 0
  const encoder = new TextEncoder()
  return {
    getReader: () => ({
      read: () => Promise.resolve(at < chunks.length ? { done: false, value: encoder.encode(chunks[at++]) } : { done: true, value: undefined }),
    }),
  }
}

function serve(chunks: string[]) {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, body: body(chunks) } as unknown as Response)))
}

describe("sweepUrl", () => {
  it("carries the room and only the filters that were set", () => {
    const url = new URL(sweepUrl({ room_width_m: 3.6, room_depth_m: 3, room_height_m: 2.4, limit: 8, category: "sofa" }), "http://localhost:3000")
    expect(url.pathname).toBe("/agent/fit/stream")
    expect(url.searchParams.get("room_width_m")).toBe("3.6")
    expect(url.searchParams.get("limit")).toBe("8")
    expect(url.searchParams.get("category")).toBe("sofa")
    expect(url.searchParams.has("price_band")).toBe(false)
  })
})

describe("streamSweep", () => {
  it("hands over every verdict the moment its own frame lands", async () => {
    serve([
      'event: start\ndata: {"event":"start","total":2}\n\n',
      'event: verdict\ndata: {"event":"verdict","sku":"A","verdict":"fits"}\n\nevent: verdict\ndata: {"event',
      '":"verdict","sku":"B","verdict":"too_large"}\n\nevent: done\ndata: {"event":"done","note":"x"}\n\n',
    ])

    const seen: string[] = []
    await streamSweep({ room_width_m: 4, room_depth_m: 3.5, room_height_m: 2.4 }, (event) => seen.push(`${event.event}:${event.sku ?? ""}`))
    expect(seen).toEqual(["start:", "verdict:A", "verdict:B", "done:"])
  })

  it("says so when the stream refuses", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, body: null } as unknown as Response)))
    await expect(streamSweep({ room_width_m: 0.4, room_depth_m: 3.5, room_height_m: 2.4 }, () => {})).rejects.toThrow(/could not be started/)
  })
})
