import Link from "next/link"

/** The page's last word: where to go next and what this shop promises, in two lines. */
export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto grid w-full max-w-7xl gap-8 px-6 py-12 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div>
          <p className="display text-2xl text-foreground">Before You Buy</p>
          <p className="mt-2 max-w-md text-sm text-pretty text-muted-foreground">
            A shop that measures first. Every verdict you see was produced by the geometry engine for the room you typed, and
            nothing on a card is guessed on its behalf.
          </p>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap items-start gap-x-8 gap-y-2 text-sm md:justify-end">
          <Link href="/store" className="text-muted-foreground transition-colors hover:text-foreground">Shop</Link>
          <Link href="/room-simulator" className="text-muted-foreground transition-colors hover:text-foreground">Fit agent</Link>
          <Link href="/workspace" className="text-muted-foreground transition-colors hover:text-foreground">3D workspace</Link>
        </nav>
      </div>
    </footer>
  )
}
