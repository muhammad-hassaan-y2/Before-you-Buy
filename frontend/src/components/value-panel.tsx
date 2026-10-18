"use client"

import { Banknote, Loader2, PackageOpen, Ruler, Undo2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PriceBand } from "@/components/visuals"
import { returnsEstimate, type ReturnsEstimate } from "@/lib/agent"
import { cn } from "@/lib/utils"

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

  return (
    <Card>
      <CardHeader>
        <CardTitle>What a fit check is worth
        </CardTitle>
        <CardDescription>
Change an assumption; the service redoes the arithmetic.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <form onSubmit={recalculate} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="value-orders" className="text-muted-foreground">
              Orders / month
            </Label>
            <Input id="value-orders" inputMode="numeric" value={orders} onChange={(event) => setOrders(event.target.value)} disabled={busy} />
          </div>

          <Slider id="value-returns" label="Returns / month (%)" value={returnRate} onChange={setReturnRate} max={60} disabled={busy} />
          <Slider id="value-prevention" label="Fit returns prevented (%)" value={prevention} onChange={setPrevention} max={100} disabled={busy} />

          <div className="space-y-2">
            <Label className="text-muted-foreground">Average order</Label>
            <div className="grid grid-cols-3 gap-2">
              {BANDS.map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={band === option}
                  aria-label={option}
                  disabled={busy}
                  onClick={() => setBand(option)}
                  className={cn(
                    "flex h-11 items-center justify-center rounded-md border transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
                    band === option ? "border-foreground bg-foreground/10" : "border-border opacity-60 hover:opacity-100",
                  )}
                >
                  <PriceBand band={option} />
                </button>
              ))}
            </div>
          </div>

          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <Banknote className="size-4" />}
            {busy ? "Adding it up…" : "Recalculate"}
          </Button>
        </form>

        {error && <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">{error}</p>}

        {estimate && (
          <div className="space-y-5">
            <Funnel estimate={estimate} />
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border text-sm">
              {(
                [
                  [Undo2, "Returns prevented / month", estimate.returns_prevented_per_month.toFixed(1)],
                  [Banknote, "Revenue kept / month", `€ ${estimate.revenue_kept_eur_per_month.toFixed(0)}`],
                  [PackageOpen, "Handling saved / month", `€ ${estimate.handling_saved_eur_per_month.toFixed(0)}`],
                  [Ruler, "Value per fit check", `€ ${estimate.per_simulation_value_eur.toFixed(3)}`],
                ] as const
              ).map(([Icon, labelText, value]) => (
                <div key={labelText} className="bg-card p-3">
                  <Icon className="size-4 text-primary" />
                  <dd className="num display mt-2 text-2xl">{value}</dd>
                  <dt className="text-[11px] text-muted-foreground">{labelText}</dt>
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

function Slider({ id, label, value, onChange, max, disabled }: { id: string; label: string; value: string; onChange: (value: string) => void; max: number; disabled: boolean }) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <Label htmlFor={id} className="text-muted-foreground">
          {label}
        </Label>
        <span className="num text-sm font-medium">{Number(value) || 0} %</span>
      </div>
      <input
        id={id}
        type="range"
        min={0}
        max={max}
        step={1}
        value={Number(value) || 0}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      />
    </div>
  )
}

/** Orders narrow to returns, to the ones the fit caused, to the ones a check would have stopped. */
function Funnel({ estimate }: { estimate: ReturnsEstimate }) {
  const total = Math.max(1, estimate.orders_per_month)
  const rows = [
    { label: "orders", value: estimate.orders_per_month, tone: "bg-foreground/70" },
    { label: "returned", value: estimate.returns_per_month, tone: "bg-warning" },
    { label: "because of fit", value: estimate.fit_driven_returns_per_month, tone: "bg-destructive/80" },
    { label: "a check would stop", value: estimate.returns_prevented_per_month, tone: "bg-success" },
  ]
  return (
    <ul className="space-y-2" aria-label="From orders to prevented returns">
      {rows.map((row) => (
        <li key={row.label} className="flex items-center gap-3">
          <span className="w-32 shrink-0 text-xs text-muted-foreground">{row.label}</span>
          <span className="h-6 flex-1 rounded-sm bg-muted/60">
            <span className={cn("block h-full rounded-sm", row.tone)} style={{ width: `${Math.max(1.5, (row.value / total) * 100)}%` }} />
          </span>
          <span className="num w-12 text-right text-xs">{Number(row.value.toFixed(1))}</span>
        </li>
      ))}
    </ul>
  )
}
