import type { Metadata } from "next"

import { AgentChat } from "@/components/agent-chat"
import { AgentSurface } from "@/components/agent-surface"
import { FitAgent } from "@/components/fit-agent"
import { RoomSimulator } from "@/components/room-simulator"

export const metadata: Metadata = {
  title: "Buy You Before — Room Simulator",
  description:
    "Tell the fit agent what you are looking for. It reads the listing, measures the room and tests the footprint before you buy.",
}

export default function RoomSimulatorPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10 lg:py-14">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight lg:text-4xl">The fit agent</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            An agent shortlists the catalog, runs a real fit simulation for each candidate through the same API your
            shoppers use, and only recommends what the geometry says fits. Every step is shown, including the ones that
            were skipped.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">agent-service · api-gateway · inference-service · geometry-service</p>
      </header>

      <section className="mb-10">
        <FitAgent />
      </section>

      <section className="mb-10 grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <AgentChat />
        <AgentSurface />
      </section>

      <section>
        <h2 className="mb-1 text-lg font-semibold tracking-tight">Or measure one piece yourself</h2>
        <p className="mb-5 max-w-2xl text-sm text-muted-foreground">
          Paste a product link or attach a room photo and the six-service pipeline does the geometry on that single item —
          the same call the agent makes when it tests a candidate.
        </p>
        <RoomSimulator />
      </section>
    </div>
  )
}
