"use client"

import { Monitor, Moon, Sun } from "lucide-react"
import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"

export type Theme = "light" | "dark" | "system"

export const THEME_KEY = "byb-theme"

/** Runs before first paint (inlined in the layout), so a stored choice never flashes the other theme. */
export const THEME_BOOT = `try{var t=localStorage.getItem("${THEME_KEY}");var d=t==="dark"||((t!=="light")&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d)}catch(e){document.documentElement.classList.add("dark")}`

function apply(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", dark)
}

const OPTIONS: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light theme", Icon: Sun },
  { value: "system", label: "Match system theme", Icon: Monitor },
  { value: "dark", label: "Dark theme", Icon: Moon },
]

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system")

  useEffect(() => {
    try {
      const stored = localStorage.getItem(THEME_KEY)
      // Reading the stored choice after mount keeps the server and first client render identical.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (stored === "light" || stored === "dark") setTheme(stored)
    } catch {
      // storage blocked: the toggle still works for this visit
    }
  }, [])

  useEffect(() => {
    if (theme !== "system") return
    const query = matchMedia("(prefers-color-scheme: dark)")
    const follow = () => apply("system")
    query.addEventListener("change", follow)
    return () => query.removeEventListener("change", follow)
  }, [theme])

  function choose(next: Theme) {
    setTheme(next)
    apply(next)
    try {
      if (next === "system") localStorage.removeItem(THEME_KEY)
      else localStorage.setItem(THEME_KEY, next)
    } catch {
      // storage blocked
    }
  }

  return (
    <div role="radiogroup" aria-label="Theme" className="flex items-center rounded-full border border-border bg-foreground/[0.04] p-0.5">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={theme === value}
          aria-label={label}
          title={label}
          onClick={() => choose(value)}
          className={cn(
            "flex size-6 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
            theme === value && "bg-foreground text-background hover:text-background",
          )}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  )
}
