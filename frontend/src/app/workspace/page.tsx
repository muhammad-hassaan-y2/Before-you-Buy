import type { Metadata } from "next"

import { SceneWorkspace } from "@/components/scene-workspace"

export const metadata: Metadata = {
  title: "3D workspace",
  description:
    "Stand a real SKU in your room before you buy it: three.js draws the placement the geometry worker proved, walkways and clearance included.",
}

export default function WorkspacePage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10 lg:py-14">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight lg:text-4xl">3D workspace</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          The same six services, seen from above or from eye height. scene-service turns the fit report into a scene spec —
          walls, obstacles, door swing, part boxes and camera presets — and this viewport only draws what it was given.
        </p>
      </header>
      <SceneWorkspace />
    </div>
  )
}
