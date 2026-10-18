"use client"

import { Handshake } from "lucide-react"
import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { fetchReservations, type Reservation } from "@/lib/agent"

/** The human gate, on the record. A hold only exists because a shopper said yes in their own
 *  words, and those words are stored with it - nothing here is charged or shipped. */
export function ReservationList() {
  const [items, setItems] = useState<Reservation[] | null>(null)

  useEffect(() => {
    fetchReservations().then(setItems, () => setItems([]))
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Holds waiting on a person
        </CardTitle>
        <CardDescription>
          What the agent reserved after a shopper confirmed in their own words. Each row links to
          the simulation that proved the fit, so a merchant can re-run it before accepting.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {items === null && <p className="text-sm text-muted-foreground">Reading the holds…</p>}
        {items?.length === 0 && (
          <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
            Nothing on hold yet. A hold needs the shopper&apos;s own yes, so the agent cannot take one by deciding for them.
          </p>
        )}
        {items?.map((item) => (
          <div key={item.id} className="rounded-lg border px-3 py-2.5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{item.name ?? item.sku ?? "a piece"}</span>
              {item.sku && <span className="font-mono text-xs text-muted-foreground">{item.sku}</span>}
              {item.verdict && <Badge variant="success">{item.verdict}</Badge>}
              <Badge variant="outline">{item.status.replace("_", " ")}</Badge>
            </div>
            <p className="mt-1.5 text-xs italic text-muted-foreground">“{item.confirmation}”</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
              <span>{item.created_at}</span>
              <a className="underline underline-offset-2 hover:text-foreground" href={`/api/v1/simulations/${item.simulation_id}`} target="_blank" rel="noreferrer">
                fit evidence {item.simulation_id.slice(0, 8)}
              </a>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
