/** Pure maths and palette for the 3D engine. No three.js import here, so these run in a
 *  plain unit test and on the server while the page renders.
 *
 *  The scene spec arrives in metres, y-up, with the room origin in the corner beside the door
 *  hinge - except the product parts, which are centimetres and z-up. Converting that once, here,
 *  is what keeps the renderer short. */

import type { ProductPart, SceneCamera, ScenePlacement, SceneSpec } from "@/lib/api"

/** Named materials from the parts builder, in a palette that reads on a dark stage. */
export const TONES: Record<string, string> = {
  upholstery: "#6f6a63",
  timber: "#8b6544",
  linen: "#d9d2c6",
  leg: "#3f3833",
  metal: "#8d949c",
  glass: "#9ec6d8",
  stone: "#b4ada3",
}

export type Vec3 = [number, number, number]
export type Box = { center: Vec3; size: Vec3 }

export function toneColor(tone: string): string {
  const key = (tone || "timber").toLowerCase()
  return TONES[key] ?? TONES[[...Object.keys(TONES)].find((name) => key.includes(name)) ?? ""] ?? "#8b6544"
}

/** A part (cm, z-up) as a box in the renderer's space (m, y-up). */
export function partToBox(part: ProductPart): Box {
  const [width, depth, height] = part.size_cm
  const [x, y, z] = part.offset_cm
  return {
    center: [x / 100, z / 100, y / 100],
    size: [width / 100, height / 100, depth / 100],
  }
}

export function boxesOf(parts: ProductPart[]): Box[] {
  const fallback: ProductPart[] = [{ label: "item", size_cm: [0, 0, 0], offset_cm: [0, 0, 0], tone: "timber" }]
  return (parts.length > 0 ? parts : fallback).map(partToBox)
}

/** The outer box around every part - what the clearance envelope is drawn from. */
export function boundingBox(parts: ProductPart[]): Box {
  const boxes = boxesOf(parts).filter((box) => box.size[0] > 0)
  if (boxes.length === 0) return { center: [0, 0, 0], size: [0, 0, 0] }
  const min: Vec3 = [Infinity, Infinity, Infinity]
  const max: Vec3 = [-Infinity, -Infinity, -Infinity]
  for (const box of boxes) {
    for (let axis = 0; axis < 3; axis += 1) {
      min[axis] = Math.min(min[axis], box.center[axis] - box.size[axis] / 2)
      max[axis] = Math.max(max[axis], box.center[axis] + box.size[axis] / 2)
    }
  }
  return {
    center: [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2],
    size: [max[0] - min[0], max[1] - min[1], max[2] - min[2]],
  }
}

/** The footprint plus the clearance the geometry worker demanded, on the floor plane. */
export function envelopeOf(box: Box, clearanceM: number): Box {
  return {
    center: [box.center[0], clearanceM / 2, box.center[2]],
    size: [box.size[0] + 2 * clearanceM, clearanceM, box.size[2] + 2 * clearanceM],
  }
}

export function transformOf(placement: ScenePlacement): { position: Vec3; rotationY: number } {
  return { position: placement.position_m, rotationY: (placement.rotation_deg * Math.PI) / 180 }
}

export function cameraOf(spec: SceneSpec, label: string | null): SceneCamera | null {
  if (label) {
    const named = spec.cameras.find((camera) => camera.label === label)
    if (named) return named
  }
  return spec.cameras.find((camera) => camera.label === "overview") ?? spec.cameras[0] ?? null
}

export const VERDICT_COLORS: Record<string, string> = {
  fits: "#3f8f5f",
  tight: "#c9a227",
  too_large: "#b4453a",
  blocked: "#b4453a",
}

/** Camera framing for a room with no scene yet, so the stage is never empty. */
export function defaultCamera(widthM: number, depthM: number, heightM: number): SceneCamera {
  return {
    label: "overview",
    position_m: [widthM * 1.45, heightM * 1.5, -depthM * 0.65],
    target_m: [widthM / 2, 0.45, depthM / 2],
    fov_deg: 45,
  }
}
