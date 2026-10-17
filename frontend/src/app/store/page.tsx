import { Suspense } from "react"
import type { Metadata } from "next"
import Link from "next/link"

import { StoreGrid } from "@/components/store-grid"

export const metadata: Metadata = {
  title: "Shop",
  description:
    "Every piece carries its price, margin, supplier, lead time and shelf count — and the room you name decides which ones you can actually buy.",
}

/** Quick links are URLs, not decorations: each one re-opens the shop on that shelf, and the sweep
 *  measures that shelf's pieces rather than the catalog's general best. */
const QUICK_LINKS = ["sofa", "armchair", "table", "bed", "wardrobe"]

async function StoreContent({ searchParams }: { searchParams: Promise<{ category?: string }> }) {
  const { category } = await searchParams
  const shelf = QUICK_LINKS.includes(category ?? "") ? category! : null

  return (
    <div className="w-full">
      <section className="relative isolate overflow-hidden border-b border-border/60">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(85%_75%_at_12%_0%,color-mix(in_oklab,var(--primary)_18%,transparent)_0%,transparent_62%)]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 opacity-[0.07] [background-image:linear-gradient(to_right,var(--foreground)_1px,transparent_1px),linear-gradient(to_bottom,var(--foreground)_1px,transparent_1px)] [background-size:5.5rem_5.5rem]"
        />
        <div className="mx-auto w-full max-w-7xl px-6 pt-16 pb-14 lg:pt-24 lg:pb-20">
          <p className="eyebrow text-primary">Before You Buy · the shop</p>
          <h1 className="mt-6 max-w-4xl text-6xl font-semibold tracking-[-0.045em] text-balance lg:text-8xl">
            Shop the ones that fit.
          </h1>
          <p className="mt-7 max-w-2xl text-lg text-pretty text-muted-foreground lg:text-xl">
            Price, margin, supplier, lead time and the shelf&rsquo;s own count on every listing. Name the room and the
            shop streams its best candidates through the geometry engine — a card turns green the second its own
            simulation settles, not at the end of the batch.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-x-7 gap-y-3 text-sm">
            <a href="#shelf" className="font-medium text-primary underline-offset-4 hover:underline">
              Shop the live grid
            </a>
            <Link href="/room-simulator" className="font-medium text-primary underline-offset-4 hover:underline">
              Add this shop to ChatGPT or Claude
            </Link>
            <Link href="/workspace" className="font-medium text-primary underline-offset-4 hover:underline">
              Open the 3D room
            </Link>
          </div>
          <nav aria-label="Quick links" className="mt-12 flex flex-wrap items-center gap-2">
            <Link
              href="/store"
              className={`rounded-full border px-3.5 py-1.5 text-xs transition-colors ${shelf === null ? "border-primary/60 bg-primary/10 text-foreground" : "border-border/60 text-muted-foreground hover:border-primary/40 hover:text-foreground"}`}
            >
              Everything
            </Link>
            {QUICK_LINKS.map((option) => (
              <Link
                key={option}
                href={`/store?category=${option}`}
                className={`rounded-full border px-3.5 py-1.5 text-xs transition-colors ${shelf === option ? "border-primary/60 bg-primary/10 text-foreground" : "border-border/60 text-muted-foreground hover:border-primary/40 hover:text-foreground"}`}
              >
                {option}
              </Link>
            ))}
          </nav>
        </div>
      </section>

      <section id="shelf" className="mx-auto w-full max-w-7xl scroll-mt-24 px-6 py-10 lg:py-12">
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
