"use client"

import { Check, DoorOpen, Footprints, Lightbulb, Ruler, TriangleAlert, X, type LucideIcon } from "lucide-react"

import type { FitReport } from "@/lib/api"
import { cn } from "@/lib/utils"

type Stop = { icon: LucideIcon; label: string; state: "ok" | "warn" | "bad" | "unknown"; note: string }

const STATE = {
  ok: { ring: "border-success text-success", mark: Check, bar: "bg-success" },
  warn: { ring: "border-warning text-warning", mark: TriangleAlert, bar: "bg-warning" },
  bad: { ring: "border-destructive text-destructive", mark: X, bar: "bg-destructive" },
  unknown: { ring: "border-border text-muted-foreground", mark: Ruler, bar: "bg-muted-foreground/40" },
}

/** The delivery path as a route you can read at a glance: door, floor, then the piece itself.
 *  Each stop is lit by what the fit report said about it, and a stop that fails colours the
 *  stretch of road after it. */
export function DeliveryPath({ report }: { report: FitReport }) {
  const notes: string[] = []
  if (!report.walkway_connected) notes.push("At that spot the entrance is cut off — no route stays walkable from the door.")
  if (report.isolated_pockets > 0) notes.push(`It seals off ${report.isolated_pockets} pocket${report.isolated_pockets === 1 ? "" : "s"} of floor behind it.`)
  if (report.fragile) notes.push(`It passes on these numbers and fails if reality is off by ${report.tolerance_cm} cm, so the room is worth measuring again.`)
  const stops: Stop[] = [
    {
      icon: DoorOpen,
      label: "Door",
      state: report.door_pass === "pass" ? "ok" : report.door_pass === "tight" ? "warn" : report.door_pass === "blocked" ? "bad" : "unknown",
      note: { pass: "gets through the door", tight: "doorway is tight", blocked: "cannot get through the door", unknown: "doorway not checked" }[report.door_pass] ?? "doorway not checked",
    },
    {
      icon: Footprints,
      label: "Walkways",
      state: !report.walkway_connected ? "bad" : report.isolated_pockets > 0 ? "warn" : "ok",
      note: !report.walkway_connected
        ? "entrance cut off"
        : report.isolated_pockets > 0
          ? `${report.isolated_pockets} pocket${report.isolated_pockets === 1 ? "" : "s"} sealed off`
          : "stay open",
    },
    {
      icon: Ruler,
      label: "Margin",
      state: report.fragile ? "warn" : "ok",
      note: report.fragile ? `fragile by ${report.tolerance_cm} cm` : "holds if measured loosely",
    },
  ]
  return (
    <div className="space-y-4">
      <ol className="flex items-start">
        {stops.map((stop, at) => {
          const meta = STATE[stop.state]
          const Mark = meta.mark
          return (
            <li key={stop.label} className="flex flex-1 items-start last:flex-none">
              <div className="flex w-20 flex-col items-center text-center">
                <span className={cn("relative flex size-11 items-center justify-center rounded-full border-2 bg-card", meta.ring)}>
                  <stop.icon className="size-5" />
                  <span className="absolute -right-1 -bottom-1 flex size-4 items-center justify-center rounded-full bg-card">
                    <Mark className="size-3" />
                  </span>
                </span>
                <p className="mt-2 text-xs font-medium">{stop.label}</p>
                <p className="text-[11px] leading-tight text-muted-foreground">{stop.note}</p>
              </div>
              {at < stops.length - 1 && <span aria-hidden className={cn("mt-[21px] h-0.5 flex-1 rounded-full", STATE[stop.state].bar)} />}
            </li>
          )
        })}
      </ol>

      {!report.walkway_connected && report.isolated_pockets > 0 && (
        <p className="text-xs font-medium text-warning">
          {report.isolated_pockets} pocket{report.isolated_pockets === 1 ? "" : "s"} sealed off
        </p>
      )}

      {notes.map((note) => (
        <p key={note} className="text-xs leading-relaxed text-muted-foreground">
          {note}
        </p>
      ))}

      {report.suggestions.length > 0 && (
        <ul className="space-y-1.5">
          {report.suggestions.map((suggestion) => (
            <li key={suggestion} className="flex gap-2 text-sm text-muted-foreground">
              <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-primary" />
              {suggestion}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
