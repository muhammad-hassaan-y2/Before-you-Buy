import type { Metadata } from "next"
import Link from "next/link"

import { StoreGrid } from "@/components/store-grid"

export const metadata: Metadata = {
  title: "Shop",
  description:
    "Every piece carries its price, margin, supplier and lead time — and the room you are standing in decides which ones you can actually buy.",
}

export default function StorePage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-14 lg:py-20">
      <header className="mb-12 text-center">
        <p className="eyebrow text-primary">Buy You Before · the shop</p>
        <h1 className="mx-auto mt-4 max-w-4xl text-5xl font-semibold tracking-[-0.03em] text-balance lg:text-7xl">
          The storefront that answers before you add to cart.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base text-pretty text-muted-foreground lg:text-lg">
          Dropship terms on every listing — price, margin, supplier, lead time — derived from the SKU itself, and a room
          bar that sends the best candidates through the same six services a fit agent uses. A piece only wears a green
          badge when the geometry engine cleared its walkways.
        </p>
        <p className="mx-auto mt-6 max-w-2xl text-sm text-muted-foreground">
          Prefer to shop through your own assistant?{" "}
          <Link href="/room-simulator" className="font-medium text-primary underline-offset-4 hover:underline">
            Add this shop to ChatGPT or Claude
          </Link>{" "}
          and the same terms and verdicts come back as tools.
        </p>
      </header>

      <StoreGrid />
    </div>
  )
}
