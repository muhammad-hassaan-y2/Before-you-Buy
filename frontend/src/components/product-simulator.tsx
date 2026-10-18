"use client"

import { AlertTriangle, ImageIcon, Loader2, Ruler } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { RoomDimensions } from "@/components/room-dimensions"
import { FitResult, ProgressStrip } from "@/components/fit-result"
import { SimulatingRoom } from "@/components/simulating-room"
import { AddToBag } from "@/components/bag-drawer"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { PhotoDropzone } from "@/components/ui/photo-dropzone"
import { createSimulation, pollSimulation, type CatalogRow, type Simulation } from "@/lib/api"
import { useBag } from "@/lib/bag"
import { validateRoom, type RoomErrors } from "@/lib/validate"

type Props = { row: CatalogRow }

/** The listing tests itself against the shopper's room by pasting its own URL — which is the
 *  round trip the catalog service guarantees: this link resolves back to this SKU. */
export function ProductSimulator({ row }: Props) {
  // Start from the room the shopper is shopping for, if the shop already knows it.
  const { room } = useBag()
  const [width, setWidth] = useState(String(room?.width_m ?? "4.0"))
  const [depth, setDepth] = useState(String(room?.depth_m ?? "3.5"))
  const [height, setHeight] = useState(String(room?.height_m ?? "2.4"))
  const [file, setFile] = useState<File | null>(null)
  const [roomErrors, setRoomErrors] = useState<RoomErrors>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [placement, setPlacement] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function run() {
    const { room, errors } = validateRoom({ width, depth, height })
    setRoomErrors(errors)
    if (!room) {
      setError("Fix the room measurements marked below.")
      return
    }
    controller.current?.abort()
    controller.current = new AbortController()
    setBusy(true)
    setError(null)
    setSimulation(null)
    setPlacement(null)
    try {
      const accepted = await createSimulation({
        link: row.commerce.product_url,
        file,
        roomWidthM: room.width,
        roomDepthM: room.depth,
        roomHeightM: room.height,
        notes: [row.brand, row.name, row.material].filter(Boolean).join(" "),
      })
      const settled = await pollSimulation(accepted.id, setSimulation, { signal: controller.current.signal })
      if (settled && settled.status !== "completed") {
        setError(settled.error ?? "The workers did not finish in time. Check the service logs.")
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  const report = simulation?.fit_report ?? null

  return (
    <Card className="shadow-lg shadow-black/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Ruler className="size-4 text-primary" /> Test it in your room
        </CardTitle>
        <CardDescription>
          {busy
            ? "Reading the listing, measuring the room and solving the footprint…"
            : "The same pipeline the fit agent calls, run live on this piece."}
        </CardDescription>
        <ProgressStrip status={simulation?.status} started={busy} />
      </CardHeader>

      <CardContent className="space-y-5">
        <RoomDimensions
          idPrefix="pdp"
          values={{ width, depth, height }}
          errors={roomErrors}
          disabled={busy}
          onChange={(field, value) => {
            ;({ width: setWidth, depth: setDepth, height: setHeight })[field](value)
            setRoomErrors((current) => ({ ...current, [field]: undefined }))
          }}
        />

        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">
            <ImageIcon className="size-3.5" /> Room photo (optional)
          </Label>
          <PhotoDropzone file={file} onFile={setFile} disabled={busy} hint="Drop a JPG or PNG to measure the room from, or click to choose" />
        </div>

        <Button size="lg" className="w-full" onClick={run} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : <Ruler className="size-4" />}
          {busy ? "Running simulation…" : "Simulate in my room"}
        </Button>

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Real-time simulated room appeared while simulation is processing */}
        {(busy || (simulation && !report && simulation.status !== "failed")) && (
          <SimulatingRoom
            widthM={Number(width) || 4}
            depthM={Number(depth) || 3.5}
            heightM={Number(height) || 2.4}
            status={simulation?.status ?? (busy ? "pending" : undefined)}
            productName={row.name}
            candidate={{ name: row.name, geometry: row.geometry }}
            photoName={file?.name}
          />
        )}

        {report && simulation && <FitResult simulation={simulation} placement={placement} onPlacement={setPlacement} />}

        {report && simulation && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">Bag it with this report attached — the geometry worker already cleared this piece for this room.</p>
            <AddToBag
              sku={row.sku}
              simulationId={simulation.id}
              verdict={report.verdict}
              room={{ width_m: Number(width) || 4, depth_m: Number(depth) || 3.5, height_m: Number(height) || 2.4 }}
              label="Bag this fit"
            />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
