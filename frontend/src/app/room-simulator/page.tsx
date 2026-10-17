import type { Metadata } from "next"
import type { ReactNode } from "react"

import { AgentChat } from "@/components/agent-chat"
import { AgentSurface } from "@/components/agent-surface"
import { FitAgent } from "@/components/fit-agent"
import { OrderQueue } from "@/components/order-queue"
import { ReservationList } from "@/components/reservation-list"
import { RoomSimulator } from "@/components/room-simulator"
import { ValuePanel } from "@/components/value-panel"

export const metadata: Metadata = {
  title: "Buy You Before — Room Simulator",
  description:
    "Tell the fit agent what you are looking for. It reads the listing, measures the room and tests the footprint before you buy.",
}

export default function RoomSimulatorPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-14 lg:py-20">
      <header className="mb-12 text-center">
        <p className="eyebrow text-primary">agent-service · api-gateway · inference-service · geometry-service</p>
        <h1 className="mx-auto mt-4 max-w-3xl text-4xl font-semibold tracking-[-0.03em] text-balance lg:text-6xl">The fit agent</h1>
        <p className="mx-auto mt-5 max-w-2xl text-base text-pretty text-muted-foreground lg:text-lg">
          An agent shortlists the catalog, runs a real fit simulation for each candidate through the same API your
          shoppers use, and only recommends what the geometry says fits. Every step is shown, including the ones that
          were skipped.
        </p>
      </header>

      <Section>
        <FitAgent />
      </Section>

      <Section>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <AgentChat />
          <AgentSurface />
        </div>
      </Section>

      <Section eyebrow="No agent in the loop" title="Or measure one piece yourself">
        <p className="mb-5 max-w-2xl text-sm text-muted-foreground">
          Paste a product link or attach a room photo and the six-service pipeline does the geometry on that single item —
          the same call the agent makes when it tests a candidate.
        </p>
        <RoomSimulator />
      </Section>

      <Section eyebrow="The shop's side" title="What the shop gets out of it">
        <p className="mb-5 max-w-2xl text-sm text-muted-foreground">
          The same arithmetic the <span className="font-mono text-xs">returns_estimate</span> capability hands an agent, and
          the two queues a person at the shop works through: holds and order drafts, each written after a shopper said yes in
          their own words. Both are the service&apos;s numbers, not the browser&apos;s.
        </p>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <ValuePanel />
          <div className="space-y-6">
            <ReservationList />
            <OrderQueue />
          </div>
        </div>
      </Section>
    </div>
  )
}

/** One band of the page: the heading carries the rhythm, the card inside carries the work. */
function Section({ eyebrow, title, children }: { eyebrow?: string; title?: string; children: ReactNode }) {
  return (
    <section className="mb-14 last:mb-0">
      {title && (
        <div className="mb-5">
          {eyebrow && <p className="eyebrow text-primary">{eyebrow}</p>}
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.02em]">{title}</h2>
        </div>
      )}
      {children}
    </section>
  )
}
