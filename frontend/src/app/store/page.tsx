import { Suspense } from "react"
import type { Metadata } from "next"
import Link from "next/link"
import { ArrowRight, Box, Compass, ShieldCheck, Sparkles, Zap } from "lucide-react"

import { InteractiveSimulatorEngine } from "@/components/interactive-simulator"
import { StoreGrid } from "@/components/store-grid"

export const metadata: Metadata = {
  title: "Store · Before You Buy",
  description:
    "Spatial e-commerce with real-time 2D and 3D simulation. Tested with AI against your real room dimensions before purchase.",
}

const QUICK_LINKS = ["sofa", "armchair", "table", "bed", "wardrobe"]

async function StoreContent({ searchParams }: { searchParams: Promise<{ category?: string }> }) {
  const { category } = await searchParams
  const shelf = QUICK_LINKS.includes(category ?? "") ? category! : null

  return (
    <div className="w-full">
      {/* Apple-style Dramatic Hero Section */}
      <section className="relative isolate overflow-hidden border-b border-white/10 bg-gradient-to-b from-white/[0.04] via-black to-black">
        {/* Ambient radial lighting */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 left-1/2 -z-10 h-[30rem] w-[50rem] -translate-x-1/2 rounded-full bg-primary/20 blur-[120px]"
        />

        <div className="mx-auto w-full max-w-7xl px-6 pt-20 pb-16 lg:pt-28 lg:pb-24">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">
              <Sparkles className="size-3" /> Spatial AI Commerce
            </span>
            <span className="text-xs text-zinc-400">Powered by AMD ROCm & vLLM</span>
          </div>

          <h1 className="mt-6 max-w-4xl text-5xl font-semibold tracking-[-0.04em] text-white text-balance sm:text-6xl lg:text-8xl">
            The shop that measures first.
          </h1>

          <p className="mt-6 max-w-2xl text-lg text-zinc-300 font-normal leading-relaxed text-pretty lg:text-xl">
            Never wonder if furniture will fit through your door or crowd your room.
            Our spatial AI tests listings in real-time 2D & 3D against your room footprint before checkout.
          </p>

          {/* Apple-style Call to Action Buttons */}
          <div className="mt-8 flex flex-wrap items-center gap-4 text-sm font-medium">
            <a
              href="#simulator"
              className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-black font-semibold shadow-lg shadow-white/10 transition-transform duration-200 hover:scale-[1.02] active:scale-[0.98]"
            >
              <Zap className="size-4 text-primary" /> Try 2D & 3D Simulator
            </a>
            <Link
              href="/room-simulator"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-6 py-3 text-white backdrop-blur-xl transition-colors hover:border-white/30 hover:bg-white/10"
            >
              <Sparkles className="size-4 text-primary" /> Ask AI Fit Agent <ArrowRight className="size-3.5" />
            </Link>
            <a
              href="#shelf"
              className="text-zinc-400 hover:text-white px-4 py-3 transition-colors"
            >
              Browse Catalog ↓
            </a>
          </div>

          {/* Quick Category Filter Pills */}
          <nav aria-label="Quick links" className="mt-14 flex flex-wrap items-center gap-2 border-t border-white/10 pt-8">
            <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider mr-2">Collections:</span>
            <Link
              href="/store"
              className={`rounded-full border px-4 py-1.5 text-xs font-medium transition-all ${
                shelf === null
                  ? "border-primary bg-primary text-black font-semibold shadow-sm"
                  : "border-white/10 bg-white/5 text-zinc-300 hover:border-white/25 hover:text-white"
              }`}
            >
              All Pieces
            </Link>
            {QUICK_LINKS.map((option) => (
              <Link
                key={option}
                href={`/store?category=${option}`}
                className={`rounded-full border px-4 py-1.5 text-xs font-medium capitalize transition-all ${
                  shelf === option
                    ? "border-primary bg-primary text-black font-semibold shadow-sm"
                    : "border-white/10 bg-white/5 text-zinc-300 hover:border-white/25 hover:text-white"
                }`}
              >
                {option}s
              </Link>
            ))}
          </nav>
        </div>
      </section>

      {/* Featured Interactive 2D & 3D Spatial Simulator Showcase */}
      <section id="simulator" className="mx-auto w-full max-w-7xl px-6 py-12 lg:py-16 scroll-mt-20">
        <div className="mb-6">
          <div className="flex items-center gap-2">
            <span className="eyebrow text-primary">Interactive Spatial Demo</span>
          </div>
          <h2 className="text-3xl font-semibold tracking-tight text-white mt-1">
            Simulate your space in real time
          </h2>
          <p className="text-zinc-400 text-sm mt-1 max-w-2xl">
            Switch between 2D architectural blueprint and 3D spatial orbit. Reposition and rotate furniture to test walkway clearances and door swing limits.
          </p>
        </div>

        <InteractiveSimulatorEngine />
      </section>

      {/* Live Storefront Grid */}
      <section id="shelf" className="mx-auto w-full max-w-7xl scroll-mt-24 px-6 py-12 lg:py-16 border-t border-white/10">
        <div className="mb-8">
          <div className="flex items-center gap-2">
            <span className="eyebrow text-primary">The Collection</span>
          </div>
          <h2 className="text-3xl font-semibold tracking-tight text-white mt-1">
            Curated pieces, proven by geometry
          </h2>
          <p className="text-zinc-400 text-sm mt-1">
            Toggle between studio photography and 3D CAD schematics. Every item links directly to real-time simulation.
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
