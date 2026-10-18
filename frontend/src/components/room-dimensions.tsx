"use client"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { RoomErrors, RoomField } from "@/lib/validate"

type Props = {
  idPrefix: string
  values: Record<RoomField, string>
  onChange: (field: RoomField, value: string) => void
  errors?: RoomErrors
  disabled?: boolean
}

const FIELDS: { key: RoomField; label: string }[] = [
  { key: "width", label: "Width" },
  { key: "depth", label: "Depth" },
  { key: "height", label: "Height" },
]

/** The three room measurements. Each field selects its text on focus, so tabbing through and typing
 *  replaces the number, and a wrong value is named under the field it is in. */
export function RoomDimensions({ idPrefix, values, onChange, errors = {}, disabled }: Props) {
  return (
    <div className="grid grid-cols-3 gap-3">
      {FIELDS.map(({ key, label }) => {
        const id = `${idPrefix}-${key}`
        const error = errors[key]
        return (
          <div key={key} className="space-y-1.5">
            <Label htmlFor={id} className="text-xs text-muted-foreground">
              {label} (m)
            </Label>
            <Input
              id={id}
              inputMode="decimal"
              autoComplete="off"
              value={values[key]}
              onChange={(event) => onChange(key, event.target.value)}
              onFocus={(event) => event.target.select()}
              disabled={disabled}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-error` : undefined}
              className="num text-center aria-invalid:border-destructive aria-invalid:ring-destructive/30"
            />
            {error && (
              <p id={`${id}-error`} role="alert" className="text-xs text-destructive">
                {error}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
