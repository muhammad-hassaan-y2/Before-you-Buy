import { Ruler } from "lucide-react"
import type { Metadata } from "next"

import { RoomSimulator } from "@/components/room-simulator"

export const metadata: Metadata = {
  title: "Buy You Before — Room Simulator",
  description:
    "Paste a product link or upload a room photo, and the simulator works out whether that piece actually fits before you buy it.",
}

export default function RoomSimulatorPage() {
  return (
    <section className="mx-auto w-full max-w-6xl px-6 py-10 lg:py-14">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="flex items-center gap-2 text-xs font-medium tracking-[0.14em] text-primary uppercase">
            <Ruler className="size-3.5" /> Buy you before
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight lg:text-4xl">Room simulator</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            vLLM reads the listing for real-world dimensions, Shapely tests the footprint against your walls and door
            swing, and the result lands here.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">api-gateway · inference-service · geometry-service</p>
      </header>
      <RoomSimulator />
    </section>
  )
}
