import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { FitViews } from "@/components/fit-views"
import type { FitReport, SceneSpec } from "@/lib/api"

const report = {
  room_area_m2: 14.3,
  usable_area_m2: 13.1,
  placements: [{ label: "against the long wall", ring: [[0, 0], [2, 0], [2, 0.9]], area_m2: 1.8, footprint_m2: 1.8, fits: true, centre_x_m: 1, centre_y_m: 0.45, rotation_deg: 0, walkway_m: { left: 0.9, right: 0.75, front: 0.6, back: 0.2 } }],
  conflicts: [],
  coverage_pct: 15.7,
  verdict: "fits",
  obstacles: [],
  door_swing_m: 0.85,
  door_pass: "pass",
  walkway_connected: true,
  isolated_pockets: 0,
  fragile: false,
  tolerance_cm: 2,
  suggestions: [],
} as unknown as FitReport

const scene = {
  room_width_m: 4,
  room_depth_m: 3.5,
  product_name: "KURA 3-seat sofa",
  parts: [],
  geometry: { width_cm: 200, depth_cm: 90, height_cm: 84, clearance_cm: 10 },
  placements: [{ label: "against the long wall", fits: true, position_m: [2, 0, 0.6], rotation_deg: 0, walkway_m: { front: 0.6 } }],
  cameras: [{ label: "overview", position_m: [5.8, 3.6, -2.3], target_m: [2, 0.45, 1.75], fov_deg: 45 }],
  verdict: "fits",
  coverage_pct: 15.7,
} as unknown as SceneSpec

describe("FitViews", () => {
  it("offers both views and opens on the plan", () => {
    render(<FitViews report={report} widthM={4} depthM={3.5} scene={scene} />)
    expect(screen.getByRole("button", { name: /2D plan/i })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("img", { name: /Room 4 by 3.5 metres/ })).toBeInTheDocument()
  })

  it("stands the same fit in the room when 3D is picked", () => {
    render(<FitViews report={report} widthM={4} depthM={3.5} scene={scene} />)
    fireEvent.click(screen.getByRole("button", { name: /3D room/i }))
    // happy-dom has no WebGL, which is the viewer's own way of saying it took the 3D branch.
    expect(screen.getByText(/could not open WebGL/i)).toBeInTheDocument()
    expect(screen.queryByRole("img", { name: /Room 4 by 3.5 metres/ })).not.toBeInTheDocument()
  })

  it("opens straight in the room when the fit starts there", () => {
    render(<FitViews report={report} widthM={4} depthM={3.5} scene={scene} start="3d" />)
    expect(screen.getByRole("button", { name: /3D room/i })).toHaveAttribute("aria-pressed", "true")
  })

  it("refuses a 3D view for a fit that has no scene", () => {
    render(<FitViews report={report} widthM={4} depthM={3.5} />)
    expect(screen.getByRole("button", { name: /3D room/i })).toBeDisabled()
    expect(screen.getByRole("img", { name: /Room 4 by 3.5 metres/ })).toBeInTheDocument()
  })
})
