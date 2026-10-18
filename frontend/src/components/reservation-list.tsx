"use client"

import { CheckCircle2, Inbox } from "lucide-react"
import { useEffect, useState } from "react"

import { Stages } from "@/components/visuals"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { getProductImage } from "@/lib/product-images"
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
Reserved after a shopper said yes, each with the fit that proved it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {items === null && <p className="text-sm text-muted-foreground">Reading the holds…</p>}
        {items?.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
            <Inbox className="size-7 opacity-50" />
            Nothing on hold yet
            <span className="max-w-xs text-xs">A hold needs the shopper&apos;s own yes, so the agent cannot take one for them.</span>
          </div>
        )}
        {items?.map((item) => {
          const image = item.sku ? getProductImage(item.sku, "") : null
          return (
            <div key={item.id} className="flex gap-3 rounded-lg border border-border p-3 text-sm">
              <div className="size-16 shrink-0 overflow-hidden rounded-md bg-surface">
                {image && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={image.url} alt={image.alt} className="h-full w-full object-cover" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{item.name ?? item.sku ?? "a piece"}</span>
                  {item.sku && <span className="font-mono text-xs text-muted-foreground">{item.sku}</span>}
                  {item.verdict && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
                      <CheckCircle2 className="size-3.5" />
                      {item.verdict}
                    </span>
                  )}
                </div>
                <Stages status={item.status} steps={["pending merchant", "accepted", "released"]} />
                <p className="mt-2 text-xs italic text-muted-foreground">“{item.confirmation}”</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                  <span>{item.created_at}</span>
                  <a className="underline underline-offset-2 hover:text-foreground" href={`/api/v1/simulations/${item.simulation_id}`} target="_blank" rel="noreferrer">
                    fit evidence {item.simulation_id.slice(0, 8)}
                  </a>
                </div>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
