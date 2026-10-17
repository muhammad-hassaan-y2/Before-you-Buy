"use client"

import { Box, LayoutGrid } from "lucide-react"
import { useState } from "react"

import { RoomPlan } from "@/components/room-plan"
import { SceneViewer } from "@/components/scene-viewer"
import { Button } from "@/components/ui/button"
import type { FitPlacement, FitReport, Obstacle, SceneSpec } from "@/lib/api"

export type FitView = "2d" | "3d"

const VIEWS: { key: FitView; label: string; icon: typeof Box }[] = [
  { key: "2d", label: "2D plan", icon: LayoutGrid },
  { key: "3d", label: "3D room", icon: Box },
]

type Props = {
  report: FitReport
  widthM: number
  depthM: number
  obstacles?: Obstacle[]
  placement?: FitPlacement | null
  /** The scene-service spec. Without it there is nothing for the 3D view to draw. */
  scene?: SceneSpec | null
  /** Which view a fit opens in: the shop's simulator leads with the plan, the workspace with the room. */
  start?: FitView
}

/** One fit, two ways to look at it: the top-down plan the engine solved, or the same placement stood in the room. */
export function FitViews({ report, widthM, depthM, obstacles = [], placement, scene, start = "2d" }: Props) {
  const [view, setView] = useState<FitView>(scene ? start : "2d")

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">
          {view === "3d" ? "In the room, to scale" : "On the floor plan, to scale"}
        </p>
        <div role="group" aria-label="Fit view" className="flex gap-1.5">
          {VIEWS.map(({ key, label, icon: Icon }) => (
            <Button
              key={key}
              type="button"
              size="sm"
              variant={view === key ? "default" : "outline"}
              aria-pressed={view === key}
              disabled={key === "3d" && !scene}
              onClick={() => setView(key)}
            >
              <Icon className="size-3.5" />
              {label}
            </Button>
          ))}
        </div>
      </div>

      {view === "3d" && scene ? (
        <SceneViewer spec={scene} />
      ) : (
        <div className="rounded-lg border bg-muted/30 p-3">
          <RoomPlan widthM={widthM} depthM={depthM} report={report} placement={placement} obstacles={obstacles} />
        </div>
      )}
    </div>
  )
}
