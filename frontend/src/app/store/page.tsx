import { Suspense } from "react"
import type { Metadata } from "next"
import Link from "next/link"
import { ArrowRight } from "lucide-react"

import { HeroPlan } from "@/components/hero-plan"
import { InteractiveSimulatorEngine } from "@/components/interactive-simulator"
import { StoreGrid } from "@/components/store-grid"

export const metadata: Metadata = {
  title: "Store",
  description:
    "Spatial e-commerce with real-time 2D and 3D simulation. Tested with AI against your real room dimensions before purchase.",
}

const QUICK_LINKS = ["sofa", "armchair", "table", "bed", "wardrobe"]

async function StoreContent({ searchParams }: { searchParams: Promise<{ category?: string }> }) {
  const { category } = await searchParams
  const shelf = QUICK_LINKS.includes(category ?? "") ? category! : null

  return (
    <div className="w-full">
      {/* Hero: flat paper, copy left, drawn plan right. No glow, no gradient. */}
      <section className="border-b border-border">
        <div className="mx-auto grid w-full max-w-7xl items-center gap-12 px-6 py-16 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:py-24">
          <div>
            <p className="eyebrow text-primary">Furniture, measured before it ships</p>

            <h1 className="display mt-5 max-w-3xl text-5xl text-balance text-foreground sm:text-6xl lg:text-7xl">
              The shop that measures first.
            </h1>

            <p className="mt-6 max-w-xl text-lg leading-relaxed text-pretty text-muted-foreground">
              Every piece is tested against your room — the door it has to get through, the walkway it must leave
              clear — before you pay. The verdict on a card is the geometry engine&rsquo;s own word.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3 text-sm font-medium">
              <a
                href="#simulator"
                className="inline-flex h-12 items-center rounded-full bg-foreground px-7 text-background transition-colors hover:bg-foreground/85 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                Try the simulator
              </a>
              <Link
                href="/room-simulator"
                className="inline-flex h-12 items-center gap-2 rounded-full border border-foreground/30 px-7 text-foreground transition-colors hover:bg-foreground/5 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                Ask the fit agent <ArrowRight className="size-3.5" />
              </Link>
              <a href="#shelf" className="px-3 py-3 text-muted-foreground transition-colors hover:text-foreground">
                Browse the shelf ↓
              </a>
            </div>
          </div>
          <HeroPlan />
        </div>
      </section>

      {/* Featured Interactive 2D & 3D Spatial Simulator Showcase */}
      <section id="simulator" className="mx-auto w-full max-w-7xl px-6 py-12 lg:py-16 scroll-mt-20">
        <div className="mb-6">
          <p className="eyebrow text-muted-foreground">
            <span className="text-primary">01</span> / Simulator
          </p>
          <h2 className="display mt-2 text-3xl text-foreground lg:text-4xl">Place a piece in your room</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Switch between the 2D plan and a 3D orbit. Drag the piece around to see walkway clearances and the door swing.
          </p>
        </div>

        <InteractiveSimulatorEngine />
      </section>

      {/* Live Storefront Grid */}
      <section id="shelf" className="mx-auto w-full max-w-7xl scroll-mt-24 px-6 py-12 lg:py-16 border-t border-border">
        <div className="mb-8">
          <p className="eyebrow text-muted-foreground">
            <span className="text-primary">02</span> / The shelf
          </p>
          <h2 className="display mt-2 text-3xl text-foreground lg:text-4xl">Pieces, proven by geometry</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Switch a card between photo and schematic. Each one opens a page that tests the piece in your room.
          </p>
        </div>

        <StoreGrid key={shelf ?? "everything"} initialCategory={shelf} />
      </section>
    </div>
  )
}

export default function StorePage({ searchParams }: { searchParams: Promise<{ category?: string }> }) {
  return (
    <Suspense>
      <StoreContent searchParams={searchParams} />
    </Suspense>
  )
}
