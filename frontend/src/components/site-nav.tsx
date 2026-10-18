"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { BagButton } from "@/components/bag-drawer"
import { ThemeToggle } from "@/components/theme-toggle"
import { cn } from "@/lib/utils"

const LINKS = [
  { href: "/store", label: "Shop" },
  { href: "/room-simulator", label: "Fit agent" },
  { href: "/workspace", label: "3D workspace" },
]

/** A masthead, not a toolbar: the name sets the tone, the links sit beside it and the rule below
 *  does the separating. The current page is underlined rather than filled. */
export function SiteNav() {
  const path = usePathname()
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-x-8 gap-y-2 px-6 py-3">
        <Link href="/store" className="display text-xl text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
          Before You Buy
        </Link>

        <nav aria-label="Main" className="order-last flex items-center gap-6 text-sm sm:order-none">
          {LINKS.map((link) => {
            const active = path === link.href || path.startsWith(`${link.href}/`)
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "border-b-2 py-1 transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
                  active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {link.label}
              </Link>
            )
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <ThemeToggle />
          <BagButton />
        </div>
      </div>
    </header>
  )
}
