import type { Metadata } from "next"
import { BadgeCheck, ListFilter, MessageSquareText, Ruler } from "lucide-react"
import type { ReactNode } from "react"

import { AgentChat } from "@/components/agent-chat"
import { AgentSurface } from "@/components/agent-surface"
import { FitAgent } from "@/components/fit-agent"
import { OrderQueue } from "@/components/order-queue"
import { ReservationList } from "@/components/reservation-list"
import { RoomSimulator } from "@/components/room-simulator"
import { ValuePanel } from "@/components/value-panel"

export const metadata: Metadata = {
  title: "Fit agent",
  description:
    "Tell the fit agent what you are looking for. It reads the listing, measures the room and tests the footprint before you buy.",
}

export default function RoomSimulatorPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-14 lg:py-20">
      <header className="mb-12 max-w-3xl">
        <p className="eyebrow text-primary">Fit agent</p>
        <h1 className="display mt-4 text-4xl text-balance lg:text-6xl">The fit agent</h1>
        <ol className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4" aria-label="How the agent works">
          {[
            { icon: MessageSquareText, label: "Reads your brief", note: "in your own words" },
            { icon: ListFilter, label: "Shortlists", note: "the catalog" },
            { icon: Ruler, label: "Fits each piece", note: "in your room" },
            { icon: BadgeCheck, label: "Recommends", note: "only what fits" },
          ].map(({ icon: Icon, label, note }, at) => (
            <li key={label} className="relative">
              <span className="flex size-12 items-center justify-center rounded-full border border-primary/50 text-primary">
                <Icon className="size-5" />
              </span>
              {at < 3 && <span aria-hidden className="absolute top-6 left-14 hidden h-px w-[calc(100%-4rem)] bg-border sm:block" />}
              <p className="mt-3 text-sm font-medium">{label}</p>
              <p className="text-xs text-muted-foreground">{note}</p>
            </li>
          ))}
        </ol>
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
One link or photo, one piece, the same call the agent makes.
        </p>
        <RoomSimulator />
      </Section>

      <Section eyebrow="The shop's side" title="What the shop gets out of it">
        <p className="mb-5 max-w-2xl text-sm text-muted-foreground">
What a fit check saves, and the two queues a person at the shop works through.
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
          <h2 className="display mt-2 text-3xl">{title}</h2>
        </div>
      )}
      {children}
    </section>
  )
}
