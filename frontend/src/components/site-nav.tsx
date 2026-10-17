"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { BagButton } from "@/components/bag-drawer"

const LINKS = [
  { href: "/store", label: "Shop" },
  { href: "/room-simulator", label: "Fit agent" },
  { href: "/workspace", label: "3D workspace" },
]

/** Three doors, one bar: the shop a person browses, the agent that shops for them, and the room
 *  they stand pieces in. A link stays lit for anything under its own path. */
export function SiteNav() {
  const path = usePathname()
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3">
        <Link href="/store" className="text-sm font-semibold tracking-[0.18em] text-primary uppercase">
          Before you buy
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={
                path === link.href || path.startsWith(`${link.href}/`)
                  ? "rounded-full bg-secondary px-3 py-1 font-medium text-secondary-foreground"
                  : "rounded-full px-3 py-1 text-muted-foreground transition-colors hover:text-foreground"
              }
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4">
          <span className="hidden text-xs text-muted-foreground md:inline">AMD · vLLM · Evolus</span>
          <BagButton />
        </div>
      </div>
    </header>
  )
}
