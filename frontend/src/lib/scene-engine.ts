"use client"

/** The engine layer: three.js, an orbit camera and the geometry the pipeline measured.
 *
 *  Nothing here decides whether a piece fits - it draws the placement rings, obstacles and
 *  clearances the geometry and scene workers already produced. That keeps the picture and the
 *  verdict impossible to disagree about. */

import * as THREE from "three"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js"

import type { SceneSpec } from "@/lib/api"
import { boundingBox, boxesOf, cameraOf, envelopeOf, partToBox, toneColor, transformOf, VERDICT_COLORS } from "@/lib/scene"

const FLOOR = "#231f1b"
const WALL = "#322c26"
const GRID = "#4a423a"
const OBSTACLE = "#5b5147"
const DARK = "#0f0d0c"

export class RoomEngine {
  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private camera = new THREE.PerspectiveCamera(45, 1, 0.05, 200)
  private controls: OrbitControls
  private stage = new THREE.Group()
  private product = new THREE.Group()
  private envelope: THREE.LineSegments | null = null
  private spec: SceneSpec | null = null
  private showEnvelope = true
  private frame = 0
  private observer: ResizeObserver | null = null
  private fly: { from: THREE.Vector3; to: THREE.Vector3; target: THREE.Vector3; started: number } | null = null

  constructor(private canvas: HTMLCanvasElement, spec: SceneSpec | null) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap

    this.scene.background = new THREE.Color(DARK)
    this.scene.fog = new THREE.Fog(DARK, 12, 42)
    this.scene.add(this.stage, this.product)

    this.controls = new OrbitControls(this.camera, canvas)
    this.controls.enableDamping = true
    this.controls.dampingFactor = 0.08
    this.controls.maxPolarAngle = Math.PI / 2.05

    this.addLights()
    this.resize()
    if (spec) this.setSpec(spec)
    this.loop()
  }

  setSpec(spec: SceneSpec) {
    this.spec = spec
    this.rebuildStage()
    this.rebuildProduct()
    this.showPlacement(this.bestPlacement(spec))
    this.setCamera(null)
  }

  showPlacement(label: string | null) {
    if (!this.spec) return
    const spot = this.spec.placements.find((placement) => placement.label === label) ?? null
    const transform = spot ? transformOf(spot) : { position: [this.spec.room_width_m / 2, 0, this.spec.room_depth_m / 2] as [number, number, number], rotationY: 0 }
    this.product.position.set(...transform.position)
    this.product.rotation.y = transform.rotationY
    const tone = spot && !spot.fits ? "#b4453a" : null
    this.product.traverse((node) => {
      if (node instanceof THREE.Mesh) (node.material as THREE.MeshStandardMaterial).color.set(tone ?? (node.userData.base as string))
    })
    if (this.envelope) this.envelope.visible = this.showEnvelope
  }

  setCamera(label: string | null) {
    if (!this.spec) return
    const preset = cameraOf(this.spec, label)
    if (!preset) return
    this.camera.fov = preset.fov_deg
    this.camera.updateProjectionMatrix()
    const to = new THREE.Vector3(...preset.position_m)
    const target = new THREE.Vector3(...preset.target_m)
    this.fly = { from: this.camera.position.clone(), to, target, started: performance.now() }
  }

  toggleEnvelope(visible: boolean) {
    this.showEnvelope = visible
    if (this.envelope) this.envelope.visible = visible
  }

  dispose() {
    cancelAnimationFrame(this.frame)
    this.observer?.disconnect()
    this.controls.dispose()
    this.scene.traverse((node) => {
      if (node instanceof THREE.Mesh || node instanceof THREE.LineSegments) {
        node.geometry.dispose()
        const materials = Array.isArray(node.material) ? node.material : [node.material]
        materials.forEach((material) => material.dispose())
      }
    })
    this.renderer.dispose()
  }

  private bestPlacement(spec: SceneSpec): string | null {
    const fitting = spec.placements.filter((spot) => spot.fits)
    if (fitting.length > 0) {
      return fitting.reduce((best, spot) => (Math.min(...Object.values(spot.walkway_m)) > Math.min(...Object.values(best.walkway_m)) ? spot : best)).label
    }
    return spec.placements[0]?.label ?? null
  }

  private addLights() {
    this.scene.add(new THREE.HemisphereLight(0xf2ead9, 0x141210, 0.75))
    const key = new THREE.DirectionalLight(0xfff2d8, 1.25)
    key.position.set(4, 8, 3)
    key.castShadow = true
    key.shadow.mapSize.set(1024, 1024)
    key.shadow.camera.near = 0.5
    key.shadow.camera.far = 30
    key.shadow.camera.left = -8
    key.shadow.camera.right = 8
    key.shadow.camera.top = 8
    key.shadow.camera.bottom = -8
    this.scene.add(key, key.target)
    const fill = new THREE.DirectionalLight(0x9fc4e0, 0.35)
    fill.position.set(-5, 3, -4)
    this.scene.add(fill)
  }

  private rebuildStage() {
    this.clear(this.stage)
    if (!this.spec) return
    const { room_width_m: width, room_depth_m: depth, room_height_m: height, walls, door_swing_m: swing } = this.spec

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(width, depth),
      new THREE.MeshStandardMaterial({ color: FLOOR, roughness: 0.95, metalness: 0 }),
    )
    floor.rotation.x = -Math.PI / 2
    floor.position.set(width / 2, 0, depth / 2)
    floor.receiveShadow = true
    this.stage.add(floor)

    const grid = new THREE.GridHelper(Math.max(width, depth), Math.round(Math.max(width, depth) * 2), GRID, GRID)
    grid.position.set(width / 2, 0.002, depth / 2)
    grid.scale.set(width / Math.max(width, depth), 1, depth / Math.max(width, depth))
    ;(grid.material as THREE.Material).opacity = 0.25
    ;(grid.material as THREE.Material).transparent = true
    this.stage.add(grid)

    // Two walls keep the room legible; the other two stay open so the camera can look in.
    this.stage.add(this.wallAt(width, height, [width / 2, height / 2, 0], 0))
    this.stage.add(this.wallAt(depth, height, [0, height / 2, depth / 2], Math.PI / 2))

    for (const obstacle of walls) {
      const shape = new THREE.Shape(obstacle.ring.map(([x, y]) => new THREE.Vector2(x, y)))
      const geometry = new THREE.ExtrudeGeometry(shape, { depth: Math.max(obstacle.height_m, 0.2), bevelEnabled: false })
      geometry.rotateX(Math.PI / 2)
      geometry.translate(0, Math.max(obstacle.height_m, 0.2), 0)
      const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: OBSTACLE, roughness: 0.9, transparent: true, opacity: 0.62 }))
      mesh.castShadow = mesh.receiveShadow = true
      this.stage.add(mesh)
    }

    const swingGeometry = new THREE.RingGeometry(0, swing, 32, 1, 0, Math.PI / 2)
    swingGeometry.rotateX(Math.PI / 2)
    const arc = new THREE.Mesh(swingGeometry, new THREE.MeshBasicMaterial({ color: "#c9a227", transparent: true, opacity: 0.22, side: THREE.DoubleSide }))
    arc.position.set(0, 0.015, 0)
    this.stage.add(arc)

    this.camera.updateProjectionMatrix()
  }

  private wallAt(length: number, height: number, position: [number, number, number], rotationY: number) {
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(length, height, 0.06),
      new THREE.MeshStandardMaterial({ color: WALL, roughness: 0.85, transparent: true, opacity: 0.5 }),
    )
    mesh.position.set(...position)
    mesh.rotation.y = rotationY
    mesh.receiveShadow = true
    return mesh
  }

  private rebuildProduct() {
    this.clear(this.product)
    this.envelope = null
    if (!this.spec) return

    for (const part of this.spec.parts.length > 0 ? this.spec.parts : []) {
      const box = partToBox(part)
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(...box.size),
        new THREE.MeshStandardMaterial({ color: toneColor(part.tone), roughness: part.tone === "metal" ? 0.35 : 0.78, metalness: part.tone === "metal" ? 0.55 : 0.02 }),
      )
      mesh.position.set(...box.center)
      mesh.castShadow = mesh.receiveShadow = true
      mesh.userData.base = toneColor(part.tone)
      mesh.userData.label = part.label
      this.product.add(mesh)
    }

    if (boxesOf(this.spec.parts).length === 0) {
      const geometry = new THREE.BoxGeometry(this.spec.geometry.width_cm / 100, this.spec.geometry.height_cm / 100, this.spec.geometry.depth_cm / 100)
      const material = new THREE.MeshStandardMaterial({ color: toneColor("timber"), roughness: 0.8 })
      const single = new THREE.Mesh(geometry, material)
      single.position.set(0, this.spec.geometry.height_cm / 200, 0)
      single.castShadow = single.receiveShadow = true
      single.userData.base = toneColor("timber")
      this.product.add(single)
    }

    const envelope = envelopeOf(boundingBox(this.spec.parts), this.spec.clearance_m)
    const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(...envelope.size))
    this.envelope = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: VERDICT_COLORS[this.spec.verdict] ?? "#c9a227" }))
    this.envelope.position.set(...envelope.center)
    this.envelope.visible = this.showEnvelope
    this.product.add(this.envelope)
  }

  private resize() {
    const parent = this.canvas.parentElement
    const width = parent?.clientWidth ?? this.canvas.clientWidth ?? 640
    const height = parent?.clientHeight ?? this.canvas.clientHeight ?? 420
    this.renderer.setSize(width, height, false)
    this.camera.aspect = width / Math.max(height, 1)
    this.camera.updateProjectionMatrix()
    if (typeof ResizeObserver !== "undefined" && parent) {
      this.observer = new ResizeObserver(() => this.resize())
      this.observer.observe(parent)
    }
  }

  private loop = () => {
    this.frame = requestAnimationFrame(this.loop)
    if (this.fly) {
      const elapsed = (performance.now() - this.fly.started) / 600
      const t = Math.min(elapsed, 1)
      const eased = t * t * (3 - 2 * t)
      this.camera.position.lerpVectors(this.fly.from, this.fly.to, eased)
      this.controls.target.lerp(this.fly.target, eased * 0.4 + 0.1)
      if (t >= 1) this.fly = null
    }
    this.controls.update()
    this.renderer.render(this.scene, this.camera)
  }

  private clear(group: THREE.Group) {
    group.traverse((node) => {
      if (node instanceof THREE.Mesh || node instanceof THREE.LineSegments) {
        node.geometry.dispose()
        const materials = Array.isArray(node.material) ? node.material : [node.material]
        materials.forEach((material) => material.dispose())
      }
    })
    group.clear()
  }
}
