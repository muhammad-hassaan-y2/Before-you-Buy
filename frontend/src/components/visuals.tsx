import type { StockRow } from "@/lib/api"
import { cn } from "@/lib/utils"

const TONE: Record<string, { fill: string; stroke: string; text: string }> = {
  fits: { fill: "fill-success/25", stroke: "stroke-success", text: "text-success" },
  tight: { fill: "fill-warning/30", stroke: "stroke-warning", text: "text-warning" },
  too_large: { fill: "fill-destructive/25", stroke: "stroke-destructive", text: "text-destructive" },
  blocked: { fill: "fill-destructive/25", stroke: "stroke-destructive", text: "text-destructive" },
  none: { fill: "fill-muted-foreground/20", stroke: "stroke-muted-foreground", text: "text-muted-foreground" },
}

/** The piece drawn at scale inside the room on the bar: what a shopper would otherwise have to
 *  picture from "180 × 89 cm" and "4 × 3.5 m". Walkway gaps are the space left either side. */
export function FootprintPlan({
  roomW,
  roomD,
  pieceWcm,
  pieceDcm,
  verdict,
  className,
}: {
  roomW: number
  roomD: number
  pieceWcm: number
  pieceDcm: number
  verdict?: string
  className?: string
}) {
  const tone = TONE[verdict ?? "none"] ?? TONE.none
  const pw = pieceWcm / 100
  const pd = pieceDcm / 100
  const over = pw > roomW || pd > roomD
  // Draw in room metres; viewBox adds a margin for the dimension ticks.
  const m = 0.35
  const vw = roomW + m * 2
  const vh = roomD + m * 2
  const x = Math.max(0, (roomW - pw) / 2)
  const y = Math.max(0.55, roomD - pd - 0.25)
  const gap = Math.max(0, (roomW - pw) / 2)
  return (
    <svg
      viewBox={`0 0 ${vw} ${vh}`}
      role="img"
      aria-label={`${pieceWcm.toFixed(0)} by ${pieceDcm.toFixed(0)} centimetres in a ${roomW} by ${roomD} metre room${over ? ", larger than the room" : `, ${gap.toFixed(2)} metres left each side`}`}
      className={cn("h-auto w-full", className)}
    >
      <g transform={`translate(${m} ${m})`}>
        <rect width={roomW} height={roomD} className="fill-surface stroke-muted-foreground/60" strokeWidth={0.05} />
        {/* door swing, bottom-left */}
        <path d={`M0 ${roomD} L0 ${roomD - 0.85} A0.85 0.85 0 0 1 0.85 ${roomD} Z`} className="fill-primary/10 stroke-primary/40" strokeWidth={0.03} strokeDasharray="0.08 0.08" />
        <rect x={x} y={y} width={pw} height={pd} rx={0.06} className={cn(tone.fill, tone.stroke)} strokeWidth={0.06} />
        {!over && gap > 0.05 && (
          <>
            <path d={`M0.04 ${y + pd / 2} H${x - 0.04} M${x + pw + 0.04} ${y + pd / 2} H${roomW - 0.04}`} className={tone.stroke} strokeWidth={0.035} strokeDasharray="0.1 0.08" />
          </>
        )}
      </g>
    </svg>
  )
}

/** One dot per unit of stock: filled when free, ringed when held. Counts above twelve collapse
 *  into a number, because a row of forty dots says less than "40". */
export function StockDots({ stock }: { stock?: StockRow }) {
  if (!stock) return <span className="h-2 w-16 animate-pulse rounded-full bg-muted" aria-label="Reading the shelf" />
  if (stock.state === "made_to_order") {
    return (
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground" title={`Cut after your order · ${stock.lead_days} days`}>
        <span className="h-px w-6 border-t border-dashed border-muted-foreground" aria-hidden /> made to order
      </span>
    )
  }
  const shown = Math.min(stock.on_hand, 12)
  const tone = stock.state === "in_stock" ? "bg-success" : stock.state === "low" ? "bg-warning" : "bg-destructive"
  return (
    <span className="flex items-center gap-1.5" role="img" aria-label={`${stock.available} available, ${stock.reserved} held, ${stock.on_hand} on the floor`}>
      {shown === 0 ? (
        <span className="text-xs text-destructive">out · next lot {stock.next_lot_in_days}d</span>
      ) : (
        Array.from({ length: shown }).map((_, at) => (
          <span key={at} className={cn("size-2 rounded-full", at < stock.available ? tone : "border border-muted-foreground bg-transparent")} />
        ))
      )}
      {stock.on_hand > 12 && <span className="num text-xs text-muted-foreground">+{stock.on_hand - 12}</span>}
    </span>
  )
}

/** Days to the door against a 30-day track: the longer the wait, the further the marker sits. */
export function LeadBar({ days, max = 30 }: { days: number; max?: number }) {
  const at = Math.min(1, days / max)
  return (
    <span className="flex items-center gap-2" role="img" aria-label={`Ships in ${days} days`}>
      <span className="relative h-1.5 w-20 rounded-full bg-muted">
        <span className="absolute inset-y-0 left-0 rounded-full bg-foreground/70" style={{ width: `${at * 100}%` }} />
      </span>
      <span className="num text-xs text-muted-foreground">{days}d</span>
    </span>
  )
}

/** €, €€ or €€€ as three coins, so a band reads before it is read. */
export function PriceBand({ band }: { band?: string | null }) {
  const level = (band ?? "").length || 0
  if (!level) return null
  return (
    <span className="inline-flex items-center gap-1" role="img" aria-label={`Price tier ${level} of 3`}>
      {[1, 2, 3].map((tier) => (
        <span key={tier} className={cn("size-3 rounded-full border", tier <= level ? "border-foreground bg-foreground" : "border-muted-foreground/50")} />
      ))}
    </span>
  )
}

/** What the retail price is made of: cost to the shop, then margin. */
export function PriceSplit({ cost, margin }: { cost: number; margin: number }) {
  const total = cost + margin
  const costPct = total ? (cost / total) * 100 : 0
  return (
    <div className="space-y-2">
      <div className="flex h-3 overflow-hidden rounded-full" role="img" aria-label={`Cost ${cost} euro, margin ${margin} euro`}>
        <span className="bg-foreground/70" style={{ width: `${costPct}%` }} />
        <span className="flex-1 bg-primary" />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>
          <span className="mr-1.5 inline-block size-2 rounded-full bg-foreground/70" />
          Cost <span className="num text-foreground">€{cost.toFixed(0)}</span>
        </span>
        <span>
          <span className="mr-1.5 inline-block size-2 rounded-full bg-primary" />
          Margin <span className="num text-foreground">€{margin.toFixed(0)}</span>
        </span>
      </div>
    </div>
  )
}

/** Plan and elevation of the piece with its dimensions drawn on, instead of a table of numbers. */
export function SpecFigure({ w, d, h, clearance }: { w: number; d: number; h: number; clearance: number }) {
  const scale = 150 / Math.max(w, d + h, 1)
  const W = w * scale
  const D = d * scale
  const H = h * scale
  const pad = 28
  const gap = 36
  const vw = Math.max(W, 120) + pad * 2 + 30
  const vh = D + H + gap + pad * 2
  const c = Math.max(2, clearance * scale)
  return (
    <svg viewBox={`0 0 ${vw} ${vh}`} role="img" aria-label={`${w} wide, ${d} deep, ${h} high, in centimetres`} className="h-auto w-full max-w-[17rem]">
      <g transform={`translate(${pad} ${pad})`} className="text-muted-foreground">
        {/* plan */}
        <rect x={-c} y={-c} width={W + c * 2} height={D + c * 2} className="fill-none stroke-primary/50" strokeDasharray="4 4" />
        <rect width={W} height={D} rx={3} className="fill-primary/15 stroke-primary" strokeWidth={1.5} />
        <path d={`M0 ${D + c + 10} H${W}`} className="stroke-current" />
        <path d={`M0 ${D + c + 6} v8 M${W} ${D + c + 6} v8`} className="stroke-current" />
        <text x={W / 2} y={D + c + 24} textAnchor="middle" className="fill-foreground" fontSize="11">{w.toFixed(0)} cm</text>
        <path d={`M${W + c + 10} 0 V${D}`} className="stroke-current" />
        <path d={`M${W + c + 6} 0 h8 M${W + c + 6} ${D} h8`} className="stroke-current" />
        <text x={W + c + 18} y={D / 2} className="fill-foreground" fontSize="11" dominantBaseline="middle">{d.toFixed(0)}</text>
        {/* elevation */}
        <g transform={`translate(0 ${D + gap + 20})`}>
          <rect y={0} width={W} height={H} rx={3} className="fill-foreground/10 stroke-foreground/60" strokeWidth={1.5} />
          <path d={`M${W + 10} 0 V${H}`} className="stroke-current" />
          <path d={`M${W + 6} 0 h8 M${W + 6} ${H} h8`} className="stroke-current" />
          <text x={W + 18} y={H / 2} className="fill-foreground" fontSize="11" dominantBaseline="middle">{h.toFixed(0)}</text>
        </g>
      </g>
    </svg>
  )
}

/** A bar for a share of something, with its number beside it. */
export function Meter({ value, max = 100, label, tone = "primary" }: { value: number; max?: number; label: string; tone?: "primary" | "success" | "warning" | "destructive" }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  const color = { primary: "bg-primary", success: "bg-success", warning: "bg-warning", destructive: "bg-destructive" }[tone]
  return (
    <div role="img" aria-label={label} className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
      <div className={cn("h-full rounded-full transition-[width] duration-500 ease-out", color)} style={{ width: `${pct}%` }} />
    </div>
  )
}
