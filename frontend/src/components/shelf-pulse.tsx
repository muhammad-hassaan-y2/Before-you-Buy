"use client"

import { cn } from "@/lib/utils"

/** The shop's heartbeat, drawn rather than claimed: a pulse that only exists while catalog-service
 *  is answering, and a count of the SKUs it answered for. */
export function ShelfPulse({ live, counts, className }: { live: boolean; counts?: number; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-xs font-medium", live ? "text-success" : "text-muted-foreground", className)}>
      <span className="relative flex size-2">
        {live && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />}
        <span className={cn("relative inline-flex size-2 rounded-full", live ? "bg-success" : "bg-muted-foreground")} />
      </span>
      {live ? `shelf live · ${counts ?? 0} counts` : "shelf offline"}
    </span>
  )
}
