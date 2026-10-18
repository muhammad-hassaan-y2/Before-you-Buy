/** Checks on what a shopper types, so a wrong value is named instead of quietly replaced by a default. */

export type RoomField = "width" | "depth" | "height"
export type RoomErrors = Partial<Record<RoomField, string>>
export type Room = Record<RoomField, number>

/** Metres, inclusive. Wide enough for a hall, narrow enough that a typo (400 for 4.0) is caught. */
export const ROOM_LIMITS: Record<RoomField, readonly [number, number]> = {
  width: [1, 30],
  depth: [1, 30],
  height: [1.8, 6],
}

/** "3.5" and "3,5" are numbers; "", "abc", "3 m" and "1e3" are not. */
export function parseMetres(raw: string): number | null {
  const text = raw.trim().replace(",", ".")
  if (!/^\d+(\.\d+)?$/.test(text)) return null
  return Number(text)
}

export function validateRoom(input: Record<RoomField, string>): { room: Room | null; errors: RoomErrors } {
  const errors: RoomErrors = {}
  const room = {} as Room
  for (const field of ["width", "depth", "height"] as const) {
    const [min, max] = ROOM_LIMITS[field]
    const value = parseMetres(input[field])
    if (value === null) errors[field] = "Enter a number in metres, like 3.5."
    else if (value < min || value > max) errors[field] = `Between ${min} and ${max} m.`
    else room[field] = value
  }
  return { room: Object.keys(errors).length ? null : room, errors }
}

/** A product page address, or null when it is one. Empty is the caller's call to allow. */
export function validateLink(raw: string): string | null {
  const text = raw.trim()
  if (!text) return null
  try {
    const url = new URL(text)
    if ((url.protocol === "http:" || url.protocol === "https:") && url.hostname.includes(".")) return null
  } catch {
    // fall through
  }
  return "That does not look like a product link — it should start with https://."
}

export const PHOTO_MAX_BYTES = 12 * 1024 * 1024

/** Why a dropped or chosen file cannot be a room photo, or null when it can. */
export function validatePhoto(file: { type: string; size: number }): string | null {
  if (!file.type.startsWith("image/")) return "That file is not an image — use a JPG or PNG."
  if (file.size > PHOTO_MAX_BYTES) return "That photo is over 12 MB — use a smaller one."
  return null
}
