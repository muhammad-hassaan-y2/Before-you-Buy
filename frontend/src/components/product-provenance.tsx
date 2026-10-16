"use client"

import { AlertTriangle } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { estimatedAxes, PRODUCT_SOURCE, type ProductProfile } from "@/lib/api"

/** Which model, catalog or guess produced the box the engine fitted. */
export function ProductSourceBadge({ profile }: { profile: ProductProfile }) {
  return <Badge variant="secondary">{PRODUCT_SOURCE[profile.source] ?? profile.source}</Badge>
}

function and(words: string[]): string {
  if (words.length < 2) return words[0] ?? ""
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`
}

/** Stays silent when every axis was read; speaks up when some of the numbers are a stand-in. */
export function DimensionEstimateWarning({ profile, compact = false }: { profile: ProductProfile; compact?: boolean }) {
  const estimated = estimatedAxes(profile)
  if (estimated.length === 0) return null
  const all = estimated.length === 3
  const sentence = all
    ? "None of these sizes came from the listing - they are the category default, so the fit is only as good as that guess."
    : `${and(estimated)} ${estimated.length > 1 ? "are" : "is"} a category guess, not a number read from the listing.`

  if (compact)
    return (
      <span className="inline-flex items-center gap-1 text-warning" title={sentence}>
        <AlertTriangle className="size-3.5 shrink-0" />
        {and(estimated)} estimated
      </span>
    )

  return (
    <div className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>
        {sentence} The room was measured against{" "}
        <span className="font-mono tabular-nums">
          {profile.geometry.width_cm.toFixed(0)} × {profile.geometry.depth_cm.toFixed(0)} × {profile.geometry.height_cm.toFixed(0)} cm
        </span>
        .
      </span>
    </div>
  )
}
