import type { FitPlacement, FitReport, Obstacle } from "@/lib/api"

const PADDING_M = 0.4
const DOOR_SWING_M = 0.85

type Props = {
  widthM: number
  depthM: number
  report: FitReport
  placement?: FitPlacement | null
  /** Furniture already on the floor, from the room photo or the shopper. */
  obstacles?: Obstacle[]
}

/** Top-down plan drawn straight from the Shapely polygons (metres -> SVG units). */
export function RoomPlan({ widthM, depthM, report, placement, obstacles = [] }: Props) {
  const viewBoxWidth = widthM + PADDING_M * 2
  const viewBoxHeight = depthM + PADDING_M * 2
  // SVG y grows downward; room coordinates grow away from the front wall.
  const y = (value: number) => depthM - value

  const points = (ring: [number, number][]) => ring.map(([x, ry]) => `${x},${y(ry)}`).join(" ")
  const selected = placement ?? report.placements.find((spot) => spot.fits) ?? report.placements[0]
  const fits = selected?.fits ?? false

  return (
    <svg
      viewBox={`${-PADDING_M} ${-PADDING_M} ${viewBoxWidth} ${viewBoxHeight}`}
      className="w-full"
      role="img"
      aria-label={`Room ${widthM} by ${depthM} metres, ${obstacles.length} object(s) already on the floor, ${selected?.label ?? "no placement"}`}
    >
      <defs>
        <pattern id="grid" width="0.5" height="0.5" patternUnits="userSpaceOnUse">
          <path d="M0.5 0H0V0.5" fill="none" stroke="var(--room-wall)" strokeOpacity="0.18" strokeWidth="0.01" />
        </pattern>
      </defs>

      <rect x={-PADDING_M} y={-PADDING_M} width={viewBoxWidth} height={viewBoxHeight} fill="none" />
      <rect width={widthM} height={depthM} y={y(depthM)} fill="var(--room-floor)" />
      <rect width={widthM} height={depthM} y={y(depthM)} fill="url(#grid)" />
      <rect
        width={widthM}
        height={depthM}
        y={y(depthM)}
        fill="none"
        stroke="var(--room-wall)"
        strokeWidth={0.06}
        rx={0.03}
      />

      {/* quarter-circle door sweep, hinged at the left jamb of the front wall */}
      <path
        d={`M ${DOOR_SWING_M} ${y(0)} A ${DOOR_SWING_M} ${DOOR_SWING_M} 0 0 0 0 ${y(DOOR_SWING_M)} L 0 ${y(0)} Z`}
        fill="none"
        stroke="var(--room-wall)"
        strokeOpacity="0.5"
        strokeWidth={0.02}
        strokeDasharray="0.08 0.06"
      />
      <line x1={0} y1={y(0)} x2={0} y2={y(DOOR_SWING_M)} stroke="var(--room-wall)" strokeWidth={0.05} />

      {obstacles.map((obstacle) => (
        <polygon
          key={obstacle.label}
          points={points(obstacle.ring)}
          fill="var(--room-wall)"
          fillOpacity={0.18}
          stroke="var(--room-wall)"
          strokeOpacity={0.55}
          strokeWidth={0.02}
        >
          <title>{`${obstacle.label} (${obstacle.source}), ${obstacle.height_m.toFixed(2)} m tall`}</title>
        </polygon>
      ))}

      {selected && (
        <polygon
          points={points(selected.ring)}
          fill={fits ? "var(--room-product)" : "var(--room-blocked)"}
          fillOpacity={fits ? 0.28 : 0.2}
          stroke={fits ? "var(--room-product)" : "var(--room-blocked)"}
          strokeWidth={0.045}
        />
      )}

      <text x={widthM / 2} y={y(depthM) - 0.14} textAnchor="middle" className="fill-muted-foreground" fontSize={0.2}>
        {widthM.toFixed(1)} m
      </text>
      <text x={-0.14} y={depthM / 2} textAnchor="middle" className="fill-muted-foreground" fontSize={0.2} transform={`rotate(-90 ${-0.14} ${y(depthM / 2)})`}>
        {depthM.toFixed(1)} m
      </text>
      {selected && (
        <text x={selected.ring[0][0] + 0.06} y={y(selected.ring[0][1]) + 0.24} fontSize={0.19} className="fill-foreground">
          {selected.footprint_m2.toFixed(2)} m2
        </text>
      )}
    </svg>
  )
}
