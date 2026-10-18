"use client"

import { ClipboardList } from "lucide-react"
import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { fetchOrders, type OrderSummary } from "@/lib/agent"
import { price } from "@/lib/store"

/** The other half of the gate. A checkout is a draft, not a sale: it appears here so a person at
 *  the shop can read the words the shopper typed and the margin those pieces carry before
 *  anything is bought from the supplier. */
export function OrderQueue() {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null)

  useEffect(() => {
    fetchOrders().then(setOrders, () => setOrders([]))
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Order drafts waiting on a person
        </CardTitle>
        <CardDescription>
          What checkout wrote after a shopper confirmed in their own words. Every draft cites the simulation that cleared
          each line, and no card has been taken.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {orders === null && <p className="text-sm text-muted-foreground">Reading the drafts…</p>}
        {orders?.length === 0 && (
          <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
            Nothing ordered yet. A draft needs the shopper&apos;s own yes and a cleared verdict on every line, so neither an
            agent nor this page can make one on their behalf.
          </p>
        )}
        {orders?.map((item) => (
          <div key={item.id} className="rounded-lg border px-3 py-2.5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{item.id.slice(0, 8)}</span>
              <Badge variant="secondary">{price(item.total_eur)}</Badge>
              <span className="font-mono text-xs tabular-nums text-success">+{price(item.margin_eur)}</span>
              <Badge variant="outline">{item.status.replace("_", " ")}</Badge>
            </div>
            <p className="mt-1.5 text-xs italic text-muted-foreground">“{item.confirmation}”</p>
            <p className="mt-1 text-[11px] text-muted-foreground">{item.created_at}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
