"use client"

import { Box, Sparkles } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { BagButton } from "@/components/bag-drawer"
import { cn } from "@/lib/utils"

const LINKS = [
  { href: "/store", label: "Store" },
  { href: "/room-simulator", label: "AI Fit Agent" },
  { href: "/workspace", label: "3D Workspace" },
]

export function SiteNav() {
  const path = usePathname()
  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.08] bg-black/75 backdrop-blur-2xl transition-colors">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-3.5">
        {/* Brand Logo with Apple-style micro-icon */}
        <Link href="/store" className="flex items-center gap-2 group">
          <div className="flex size-7 items-center justify-center rounded-lg border border-white/20 bg-white/10 shadow-sm transition-transform duration-300 group-hover:scale-105">
            <Box className="size-4 text-white" />
          </div>
          <span className="text-sm font-semibold tracking-[-0.01em] text-white">
            Before You Buy
          </span>
          <span className="hidden sm:inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
            <Sparkles className="size-2.5" /> AI First
          </span>
        </Link>

        {/* Center Navigation Capsule */}
        <nav className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] p-1 backdrop-blur-xl">
          {LINKS.map((link) => {
            const active = path === link.href || path.startsWith(`${link.href}/`)
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-full px-3.5 py-1 text-xs font-medium transition-all duration-200",
                  active
                    ? "bg-white text-black shadow-sm"
                    : "text-zinc-400 hover:text-white",
                )}
              >
                {link.label}
              </Link>
            )
          })}
        </nav>

        {/* Right side status & bag */}
        <div className="flex items-center gap-3">
          <span className="hidden text-[11px] text-zinc-500 lg:inline-flex items-center gap-1.5 font-mono">
            <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Spatial AI Online
          </span>
          <BagButton />
        </div>
      </div>
    </header>
  )
}
