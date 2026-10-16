"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

const LINKS = [
  { href: "/room-simulator", label: "Fit agent" },
  { href: "/workspace", label: "3D workspace" },
]

/** One bar for both doors: the agent that shops for you, and the workspace you stand pieces in. */
export function SiteNav() {
  const path = usePathname()
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/85 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3">
        <Link href="/room-simulator" className="text-sm font-semibold tracking-[0.14em] text-primary uppercase">
          Buy you before
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={
                path === link.href
                  ? "rounded-md bg-secondary px-2.5 py-1 font-medium text-secondary-foreground"
                  : "rounded-md px-2.5 py-1 text-muted-foreground transition-colors hover:text-foreground"
              }
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <span className="ml-auto text-xs text-muted-foreground">AMD · vLLM · Evolus</span>
      </div>
    </header>
  )
}
