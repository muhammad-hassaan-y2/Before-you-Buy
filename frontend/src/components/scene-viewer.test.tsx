import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { SceneViewer } from "@/components/scene-viewer"
import type { SceneSpec } from "@/lib/api"

const spec = {
  version: "1",
  room_width_m: 4,
  room_depth_m: 3.5,
  room_height_m: 2.4,
  walls: [],
  door_swing_m: 0.85,
  product_name: "KURA 3-seat sofa",
  product_category: "sofa",
  parts: [{ label: "seat cushion", size_cm: [180, 80, 35], offset_cm: [0, 5, 27], tone: "upholstery" }],
  geometry: { width_cm: 200, depth_cm: 90, height_cm: 44, clearance_cm: 10 },
  clearance_m: 0.1,
  placements: [
    { label: "against the long wall", fits: true, position_m: [2, 0, 0.6], rotation_deg: 0, walkway_m: { front: 0.6, back: 0.2, left: 0.9, right: 0.75 } },
    { label: "by the window", fits: false, position_m: [1, 0, 2.6], rotation_deg: 90, walkway_m: { front: 0.3, back: 0.1, left: 0.2, right: 0.4 } },
  ],
  cameras: [{ label: "overview", position_m: [5.8, 3.6, -2.3], target_m: [2, 0.45, 1.75], fov_deg: 45 }],
  verdict: "fits",
  coverage_pct: 14.2,
} as unknown as SceneSpec

describe("SceneViewer", () => {
  it("explains itself when the browser has no WebGL, instead of a blank box", () => {
    render(<SceneViewer spec={spec} />)
    expect(screen.getByText(/could not open WebGL/i)).toBeInTheDocument()
  })

  it("has something to say before a simulation exists", () => {
    render(<SceneViewer spec={null} />)
    expect(screen.getByText(/Nothing to place yet/i)).toBeInTheDocument()
  })
})
