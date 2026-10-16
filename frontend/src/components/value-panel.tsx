"use client"

import { Banknote, Loader2, TrendingUp } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { returnsEstimate, type ReturnsEstimate } from "@/lib/agent"

const BANDS = ["$", "$$", "$$$"]

/** The merchant's number, and the only place this app claims one. Every figure comes back from
 *  `returns_estimate` as arithmetic over the inputs below - no model forecasts a month. */
export function ValuePanel() {
  const [orders, setOrders] = useState("1000")
  const [band, setBand] = useState("$$")
  const [returnRate, setReturnRate] = useState("20")
  const [prevention, setPrevention] = useState("25")
  const [estimate, setEstimate] = useState<ReturnsEstimate | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function recalculate(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setEstimate(
        await returnsEstimate({
          ordersPerMonth: Number(orders) || 0,
          priceBand: band,
          returnRate: (Number(returnRate) || 0) / 100,
          prevention: (Number(prevention) || 0) / 100,
        }),
      )
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "agent-service is not reachable.")
    } finally {
      setBusy(false)
    }
  }

  const fields = [
    ["Orders / month", orders, setOrders],
    ["Returns / month (%)", returnRate, setReturnRate],
    ["Fit returns prevented (%)", prevention, setPrevention],
  ] as const

  return (
    <Card className="shadow-lg shadow-black/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="size-4 text-primary" /> What a fit check is worth
        </CardTitle>
        <CardDescription>
          Change the assumptions and the arithmetic follows. The service adds up what a shop saves
          when the piece is measured before the order, and says so on its own numbers.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <form onSubmit={recalculate} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {fields.map(([labelText, value, setter], index) => (
              <div key={labelText} className={index === 2 ? "col-span-2 space-y-2" : "space-y-2"}>
                <Label htmlFor={`value-${index}`} className="text-muted-foreground">
                  {labelText}
                </Label>
                <Input id={`value-${index}`} inputMode="decimal" value={value} onChange={(event) => setter(event.target.value)} disabled={busy} />
              </div>
            ))}
            <div className="space-y-2">
              <Label className="text-muted-foreground">Average order</Label>
              <div className="flex gap-1.5">
                {BANDS.map((option) => (
                  <Button key={option} type="button" size="sm" variant={band === option ? "default" : "outline"} disabled={busy} onClick={() => setBand(option)}>
                    {option}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <Banknote className="size-4" />}
            {busy ? "Adding it up…" : "Recalculate"}
          </Button>
        </form>

        {error && <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">{error}</p>}

        {estimate && (
          <div className="space-y-3">
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {(
                [
                  ["Returns prevented / month", estimate.returns_prevented_per_month.toFixed(1)],
                  ["Revenue kept / month", `€ ${estimate.revenue_kept_eur_per_month.toFixed(0)}`],
                  ["Handling saved / month", `€ ${estimate.handling_saved_eur_per_month.toFixed(0)}`],
                  ["Value per fit check", `€ ${estimate.per_simulation_value_eur.toFixed(3)}`],
                ] as const
              ).map(([labelText, value]) => (
                <div key={labelText} className="rounded-lg border p-3">
                  <dt className="text-xs text-muted-foreground">{labelText}</dt>
                  <dd className="font-mono text-base tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {estimate.orders_per_month} orders, {estimate.returns_per_month} returns,{" "}
              {estimate.fit_driven_returns_per_month} of them because it did not fit — held at{" "}
              {(estimate.assumptions.fit_driven_share_of_returns * 100).toFixed(0)} % fit-driven and{" "}
              {estimate.assumptions.handling_cost_eur_per_return} € handling per return. {estimate.assumptions.note}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
