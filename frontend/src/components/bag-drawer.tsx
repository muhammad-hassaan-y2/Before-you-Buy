"use client"

import { Loader2, ShoppingBag, X } from "lucide-react"
import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  addToBag,
  closeBag,
  dismissOrder,
  measureBag,
  openBag,
  placeOrder,
  removeFromBag,
  soundsConfirmed,
  useBag,
  type Bag,
  type BagLine,
  type BagRoom,
  type Order,
} from "@/lib/bag"
import { PASS_VERDICTS, price, verdictLabel, verdictVariant } from "@/lib/store"
import { cn } from "@/lib/utils"

/** The bag the shopper checks out with is the bag the agent fills in ChatGPT: same tool, same
 *  gate. Nothing here prices a line - the service's `_view` does - and the order button stays
 *  disabled until the shopper has typed their own yes, because checkout refuses an assumed one. */
export function BagDrawer() {
  const { bag, open, busy, error, order, room } = useBag()
  const [words, setWords] = useState("")

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeBag()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Your bag">
      <button type="button" className="flex-1 bg-background/60 backdrop-blur-[2px]" aria-label="Close the bag" onClick={closeBag} />
      <aside className="flex h-full w-full max-w-md flex-col border-l border-border/60 bg-card">
        <header className="flex items-center gap-3 border-b border-border/50 px-6 py-4">
          <h2 className="display text-xl">{order ? "Order draft" : "Your bag"}</h2>
          <Button type="button" size="icon" variant="ghost" className="ml-auto" aria-label="Close the bag" onClick={closeBag}>
            <X className="size-4" />
          </Button>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {error && <p className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
          {order ? (
            <Receipt order={order} />
          ) : !bag || bag.lines.length === 0 ? (
            <p className="rounded-md border border-dashed border-border/60 p-8 text-center text-sm text-muted-foreground">
              Nothing in the bag yet. Add a piece and its fit report comes with it.
            </p>
          ) : (
            <>
              <RoomLine bag={bag} current={room} />
              {busy && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="size-3.5 animate-spin" /> The geometry worker is measuring…
                </p>
              )}
              <ul className="space-y-3">
                {bag.lines.map((line) => (
                  <BagRow key={line.sku} line={line} busy={busy} />
                ))}
              </ul>
              {bag.set && <SetVerdict bag={bag} />}
              <Totals bag={bag} />
              <Checkout bag={bag} words={words} setWords={setWords} busy={busy} onMeasure={measureBag} onPlace={async (confirmation) => { await placeOrder(confirmation); setWords("") }} />
            </>
          )}
          {order && (
            <Button type="button" variant="outline" size="sm" onClick={dismissOrder}>
              Back to the bag
            </Button>
          )}
        </div>
      </aside>
    </div>
  )
}

function RoomLine({ bag, current }: { bag: Bag; current: Bag["room"] }) {
  const measured = bag.room.width_m === current.width_m && bag.room.depth_m === current.depth_m && bag.room.height_m === current.height_m
  return (
    <p className="text-xs text-muted-foreground">
      Measured for a{" "}
      <span className="num font-medium text-foreground">
        {bag.room.width_m} × {bag.room.depth_m} × {bag.room.height_m} m
      </span>{" "}
      room{measured ? "" : ` — the room on screen is ${current.width_m} × ${current.depth_m} m, so measure again before ordering`}
      .
    </p>
  )
}

function BagRow({ line, busy }: { line: BagLine; busy: boolean }) {
  const tightest = line.walkway_m ? Math.min(...Object.values(line.walkway_m)) : null
  return (
    <li className="rounded-lg border border-border/60 bg-background/40 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{line.name}</p>
          <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{line.sku}</p>
        </div>
        <Badge variant={verdictVariant(line.verdict ?? undefined)}>{verdictLabel(line.verdict ?? undefined)}</Badge>
      </div>
      <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="num text-sm font-semibold text-foreground">{price(line.price_eur * line.quantity)}</span>
        {tightest !== null && <span className="tabular-nums">{tightest.toFixed(2)} m walkway</span>}
        <span className="ml-auto flex items-center gap-1">
          <span className="tabular-nums">× {line.quantity}</span>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            disabled={busy}
            onClick={() => void addToBag(line.sku, { quantity: line.quantity + 1, simulationId: line.simulation_id })}
          >
            +
          </Button>
          <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-xs" disabled={busy} onClick={() => void removeFromBag(line.sku)} aria-label={`Remove ${line.name}`}>
            Remove
          </Button>
        </span>
      </div>
    </li>
  )
}

function SetVerdict({ bag }: { bag: Bag }) {
  const set = bag.set
  if (!set) return null
  return (
    <div className="rounded-lg border border-border/60 bg-muted/30 p-4">
      <div className="flex items-center gap-2">
        <p className="eyebrow text-muted-foreground">Bought together</p>
        <Badge variant={verdictVariant(set.verdict)}>{verdictLabel(set.verdict)}</Badge>
      </div>
      <p className="num mt-2 text-xs text-muted-foreground">
        {set.footprint_m2} m² on {set.usable_area_m2} m² usable · {set.coverage_pct}% covered
        {set.tightest_walkway_m !== null && ` · tightest walkway ${set.tightest_walkway_m} m`}
      </p>
      {set.conflicts.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-warning">
          {set.conflicts.map((conflict) => (
            <li key={conflict}>{conflict}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Totals({ bag }: { bag: Bag }) {
  return (
    <dl className="grid gap-1.5 border-t border-border/50 pt-4 text-sm">
      <div className="flex justify-between">
        <dt className="text-muted-foreground">{bag.items} piece(s)</dt>
        <dd className="num font-medium">{price(bag.total_eur)}</dd>
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <dt>Arrives</dt>
        <dd className="tabular-nums">
          {bag.lead_days} days, {bag.freight} freight
        </dd>
      </div>
    </dl>
  )
}

function Checkout({
  bag,
  words,
  setWords,
  busy,
  onMeasure,
  onPlace,
}: {
  bag: Bag
  words: string
  setWords: (value: string) => void
  busy: boolean
  onMeasure: () => Promise<unknown>
  onPlace: (confirmation: string) => void
}) {
  const unproven = bag.unproven.length > 0
  return (
    <div className="space-y-3 rounded-lg border border-border/60 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="eyebrow text-muted-foreground">Fit check</p>
        <Button type="button" size="sm" variant={unproven ? "default" : "outline"} disabled={busy} onClick={() => void onMeasure()}>
          {busy ? <Loader2 className="size-3.5 animate-spin" /> : null}
          {unproven ? `Measure ${bag.unproven.length} unproven` : "Re-measure the bag"}
        </Button>
      </div>
      {unproven ? (
        <p className="text-xs text-muted-foreground">
          {bag.unproven.join(", ")} {bag.unproven.length === 1 ? "has" : "have"} no cleared report for this room yet. Measure the bag first — checkout refuses an unproven line.
        </p>
      ) : (
        <div className="space-y-2">
          <Label htmlFor="bag-yes" className="text-xs text-muted-foreground">
            Your own words
          </Label>
          <Textarea id="bag-yes" rows={2} value={words} onChange={(event) => setWords(event.target.value)} placeholder="yes, order it" disabled={busy} />
          <p className="text-xs text-muted-foreground">{bag.checkout.needs} — no card is taken. A person at the shop confirms the draft.</p>
          <Button
            type="button"
            className={cn("w-full", !soundsConfirmed(words) && "opacity-60")}
            disabled={busy || !soundsConfirmed(words)}
            onClick={() => onPlace(words)}
          >
            Place the order · {price(bag.total_eur)}
          </Button>
        </div>
      )}
    </div>
  )
}

function Receipt({ order }: { order: Order }) {
  return (
    <div className="space-y-3 rounded-lg border border-success/30 bg-success/10 p-4 text-sm">
      <p className="font-medium text-success">Draft placed · awaiting the shop</p>
      <p className="text-xs text-muted-foreground">{order.next}</p>
      <ul className="space-y-1 text-xs">
        {order.proofs.map((proof) => (
          <li key={proof.sku} className="flex items-center gap-2">
            <Badge variant={verdictVariant(proof.verdict ?? undefined)}>{verdictLabel(proof.verdict ?? undefined)}</Badge>
            <span className="font-mono">{proof.sku}</span>
            <span className="text-muted-foreground">× {proof.quantity}</span>
            {proof.verify && (
              <a href={proof.verify} className="ml-auto underline-offset-4 hover:underline" target="_blank" rel="noreferrer">
                report
              </a>
            )}
          </li>
        ))}
      </ul>
      <div className="num flex justify-between border-t border-border/40 pt-2 text-sm">
        <span>{price(order.total_eur)}</span>
        <span className="text-xs text-muted-foreground">“{order.confirmation}”</span>
      </div>
    </div>
  )
}

/** The bag affordance in the nav, and the one on a card: the count and the verdicts come from the
 *  service's last answer, so the shop cannot drift out of sync with what is really in the bag. */
export function BagButton() {
  const { bag, order } = useBag()
  const items = bag?.items ?? (order ? order.lines.reduce((total, line) => total + line.quantity, 0) : 0)
  return (
    <Button type="button" size="sm" variant="outline" className="gap-2" onClick={openBag} aria-label={`Open your bag, ${items} piece${items === 1 ? "" : "s"}`}>
      <ShoppingBag className="size-3.5" />
      Bag
      <span className="font-mono tabular-nums">{items}</span>
    </Button>
  )
}

/** Add to bag, with the fit report behind it. A card that has been measured for the room on
 *  screen passes that simulation id along, so the line enters the bag already proven and the
 *  shopper never pays a GPU job for a verdict the sweep already has. */
export function AddToBag({
  sku,
  simulationId,
  room,
  verdict,
  label = "Add to bag",
  size = "sm",
  className,
}: {
  sku: string
  simulationId?: string | null
  room?: BagRoom
  verdict?: string
  label?: string
  size?: "sm" | "default" | "lg"
  className?: string
}) {
  const { busy } = useBag()
  const [added, setAdded] = useState(false)
  const blocked = verdict !== undefined && !PASS_VERDICTS.includes(verdict)

  useEffect(() => {
    if (!added) return
    const timer = window.setTimeout(() => setAdded(false), 2500)
    return () => window.clearTimeout(timer)
  }, [added])

  return (
    <Button
      type="button"
      size={size}
      variant={blocked ? "outline" : "default"}
      className={className}
      disabled={busy || blocked}
      title={blocked ? "The engine did not clear this piece for the room on screen." : undefined}
      onClick={() => {
        void addToBag(sku, { simulationId, room }).then((result) => setAdded(result.ok))
      }}
    >
      {busy ? <Loader2 className="size-3.5 animate-spin" /> : <ShoppingBag className="size-3.5" />}
      {blocked ? "Not for this room" : added ? "In the bag" : label}
    </Button>
  )
}
