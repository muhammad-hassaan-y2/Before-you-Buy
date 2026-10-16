import { describe, expect, it } from "vitest"

import type { ProductPart, SceneSpec } from "@/lib/api"
import { boundingBox, boxesOf, cameraOf, defaultCamera, envelopeOf, partToBox, toneColor, transformOf } from "@/lib/scene"

const seat: ProductPart = { label: "seat cushion", size_cm: [180, 80, 35], offset_cm: [0, 5, 27], tone: "upholstery" }
const plinth: ProductPart = { label: "plinth", size_cm: [200, 90, 10], offset_cm: [0, 0, 5], tone: "leg" }

describe("partToBox", () => {
  it("converts centimetres to metres and z-up to y-up", () => {
    const box = partToBox(seat)
    expect(box.size).toEqual([1.8, 0.35, 0.8])
    expect(box.center).toEqual([0, 0.27, 0.05])
  })
})

describe("boundingBox", () => {
  it("wraps every part of the piece", () => {
    const box = boundingBox([seat, plinth])
    expect(box.size[0]).toBeCloseTo(2.0)
    expect(box.size[1]).toBeCloseTo(0.445)
    expect(box.size[2]).toBeCloseTo(0.9)
  })

  it("is an empty box when the catalog row had no parts", () => {
    expect(boundingBox([]).size).toEqual([0, 0, 0])
  })

  it("still returns one degenerate box so the engine has something to measure", () => {
    expect(boxesOf([])).toHaveLength(1)
  })
})

describe("envelopeOf", () => {
  it("grows the footprint on every side and rests it on the floor", () => {
    const envelope = envelopeOf({ center: [1, 0.4, 0.5], size: [2, 0.8, 1] }, 0.1)
    expect(envelope.size).toEqual([2.2, 0.1, 1.2])
    expect(envelope.center).toEqual([1, 0.05, 0.5])
  })
})

describe("transformOf", () => {
  it("turns the scene's degrees into the renderer's radians", () => {
    const transform = transformOf({ label: "against the wall", fits: true, position_m: [2, 0, 1], rotation_deg: 90, walkway_m: {} })
    expect(transform.position).toEqual([2, 0, 1])
    expect(transform.rotationY).toBeCloseTo(Math.PI / 2)
  })
})

describe("cameraOf", () => {
  const spec = {
    cameras: [
      { label: "overview", position_m: [6, 3.6, -2.3], target_m: [2, 0.45, 1.75], fov_deg: 45 },
      { label: "first-person", position_m: [2, 1.62, 0.3], target_m: [2, 1.15, 3.5], fov_deg: 62 },
    ],
  } as unknown as SceneSpec

  it("prefers the requested view", () => {
    expect(cameraOf(spec, "first-person")?.fov_deg).toBe(62)
  })

  it("falls back to the overview for an unknown label", () => {
    expect(cameraOf(spec, "drone")?.label).toBe("overview")
  })

  it("says so when the scene has no cameras at all", () => {
    expect(cameraOf({ cameras: [] } as unknown as SceneSpec, null)).toBeNull()
  })
})

describe("toneColor", () => {
  it("knows the tones the parts builder emits", () => {
    expect(toneColor("upholstery")).toBe("#6f6a63")
    expect(toneColor("linen")).toBe("#d9d2c6")
  })

  it("degrades to timber for a tone the palette has never seen", () => {
    expect(toneColor("velvet")).toBe("#8b6544")
    expect(toneColor("")).toBe("#8b6544")
  })
})

describe("defaultCamera", () => {
  it("frames a room that has no scene spec yet", () => {
    const camera = defaultCamera(4, 3.5, 2.4)
    expect(camera.target_m).toEqual([2, 0.45, 1.75])
    expect(camera.position_m[1]).toBeCloseTo(3.6)
  })
})
