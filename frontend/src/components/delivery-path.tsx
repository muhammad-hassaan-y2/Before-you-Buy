"use client"

import { DoorClosed, DoorOpen, Lightbulb, Move, ShieldAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { FitReport } from "@/lib/api"

const DOOR: Record<string, { label: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
  pass: { label: "gets through the door", variant: "success" },
  tight: { label: "doorway is tight", variant: "warning" },
  blocked: { label: "cannot get through the door", variant: "destructive" },
  unknown: { label: "doorway not checked", variant: "secondary" },
}

/** The delivery path, straight off the fit report: can the box get in, can you still walk around
 *  it once it is in, and how firmly the verdict stands against a sloppy tape measure. */
export function DeliveryPath({ report }: { report: FitReport }) {
  const door = DOOR[report.door_pass] ?? DOOR.unknown
  const notes: string[] = []
  if (!report.walkway_connected) notes.push("At that spot the entrance is cut off — no route stays walkable from the door.")
  if (report.isolated_pockets > 0) notes.push(`It seals off ${report.isolated_pockets} pocket${report.isolated_pockets === 1 ? "" : "s"} of floor behind it.`)
  if (report.fragile) notes.push(`It passes on these numbers and fails if reality is off by ${report.tolerance_cm} cm, so the room is worth measuring again.`)

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={door.variant} className="gap-1.5">
          {report.door_pass === "blocked" ? <DoorClosed className="size-3" /> : <DoorOpen className="size-3" />}
          {door.label}
        </Badge>
        {report.fragile && (
          <Badge variant="warning" className="gap-1.5">
            <ShieldAlert className="size-3" /> fragile by {report.tolerance_cm} cm
          </Badge>
        )}
        {!report.walkway_connected && (
          <Badge variant="destructive" className="gap-1.5">
            <Move className="size-3" /> entrance cut off
          </Badge>
        )}
        {report.isolated_pockets > 0 && (
          <Badge variant="warning" className="gap-1.5">
            <Move className="size-3" /> {report.isolated_pockets} pocket{report.isolated_pockets === 1 ? "" : "s"} sealed off
          </Badge>
        )}
      </div>

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
