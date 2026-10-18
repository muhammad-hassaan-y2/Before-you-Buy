"use client"

import { Inbox } from "lucide-react"
import { useEffect, useState } from "react"

import { PriceSplit, Stages } from "@/components/visuals"
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
Drafts a shopper confirmed. No card has been taken.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {orders === null && <p className="text-sm text-muted-foreground">Reading the drafts…</p>}
        {orders?.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
            <Inbox className="size-7 opacity-50" />
            Nothing ordered yet
            <span className="max-w-xs text-xs">A draft needs the shopper&apos;s own yes and a cleared verdict on every line.</span>
          </div>
        )}
        {orders?.map((item) => (
          <div key={item.id} className="rounded-lg border border-border p-3 text-sm">
            <div className="flex items-baseline justify-between gap-3">
              <span className="flex items-baseline gap-2">
                <span className="num display text-2xl">{price(item.total_eur)}</span>
                <span className="num text-xs text-success">+{price(item.margin_eur)}</span>
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">{item.id.slice(0, 8)}</span>
            </div>
            <div className="mt-2">
              <PriceSplit cost={item.total_eur - item.margin_eur} margin={item.margin_eur} />
            </div>
            <Stages status={item.status} steps={["awaiting merchant", "accepted", "ordered"]} />
            <p className="mt-2 text-xs italic text-muted-foreground">“{item.confirmation}”</p>
            <p className="mt-1 text-[11px] text-muted-foreground">{item.created_at}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
