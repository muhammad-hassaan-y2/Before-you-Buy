import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { DeliveryPath } from "@/components/delivery-path"
import type { FitReport } from "@/lib/api"

const report = (over: Partial<FitReport> = {}): FitReport => ({
  room_area_m2: 14.3,
  usable_area_m2: 13.1,
  placements: [],
  conflicts: [],
  coverage_pct: 15.7,
  verdict: "fits",
  obstacles: [],
  door_swing_m: 0.85,
  door_pass: "tight",
  walkway_connected: true,
  isolated_pockets: 0,
  fragile: true,
  tolerance_cm: 2,
  suggestions: ["Re-measure carefully: this only passes if measurements are exact."],
  ...over,
})

describe("DeliveryPath", () => {
  it("names the doorway, the tolerance and what to do about them", () => {
    render(<DeliveryPath report={report()} />)
    expect(screen.getByText("doorway is tight")).toBeInTheDocument()
    expect(screen.getByText("fragile by 2 cm")).toBeInTheDocument()
    expect(screen.getByText(/fails if reality is off by 2 cm/)).toBeInTheDocument()
    expect(screen.getByText("Re-measure carefully: this only passes if measurements are exact.")).toBeInTheDocument()
  })

  it("puts a blocked delivery path in the open", () => {
    render(<DeliveryPath report={report({ door_pass: "blocked", fragile: false, suggestions: [] })} />)
    expect(screen.getByText("cannot get through the door")).toBeInTheDocument()
    expect(screen.queryByText(/fragile/)).not.toBeInTheDocument()
  })

  it("says when the room is sealed off behind the piece", () => {
    render(<DeliveryPath report={report({ door_pass: "pass", walkway_connected: false, isolated_pockets: 2 })} />)
    expect(screen.getByText("entrance cut off")).toBeInTheDocument()
    expect(screen.getByText("2 pockets sealed off")).toBeInTheDocument()
    expect(screen.getByText(/no route stays walkable from the door/)).toBeInTheDocument()
  })

  it("stays quiet when the engine found a clear path", () => {
    render(<DeliveryPath report={report({ door_pass: "pass", fragile: false, suggestions: [] })} />)
    expect(screen.getByText("gets through the door")).toBeInTheDocument()
    expect(screen.queryByText(/pocket/)).not.toBeInTheDocument()
    expect(screen.queryByText(/entrance/)).not.toBeInTheDocument()
  })
})
