import type { Metadata } from "next"

import { SceneWorkspace } from "@/components/scene-workspace"

export const metadata: Metadata = {
  title: "3D workspace",
  description:
    "Stand a real SKU in your room before you buy it: three.js draws the placement the geometry worker proved, walkways and clearance included.",
}

export default function WorkspacePage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-14 lg:py-20">
      <header className="mb-10 max-w-3xl">
        <p className="eyebrow text-primary">3D workspace</p>
        <h1 className="display mt-3 text-4xl lg:text-6xl">Stand it in the room.</h1>
        <p className="mt-4 max-w-xl text-base text-muted-foreground">
          The same fit, seen from above or from eye height. Walls, obstacles, door swing and walkways come from the geometry
          worker; this view only draws what it was given.
        </p>
      </header>
      <SceneWorkspace />
    </div>
  )
}
