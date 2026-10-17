import { expect, test } from "@playwright/test"

import { photoJourney, simulation, tools } from "./fixtures"

/** The room vision measured off the shopper's own photo: smaller than the numbers they typed. */
const photographedRoom = {
  ...simulation,
  room_scan: { ...simulation.room_scan, width_m: 3.6, depth_m: 3.0 },
  fit_report: { ...simulation.fit_report, room_area_m2: 10.8, usable_area_m2: 10.1 },
}

test.beforeEach(async ({ page }) => {
  await page.route("**/agent/tools", (route) => route.fulfill({ json: tools }))
  await page.route("**/agent/reservations**", (route) => route.fulfill({ json: [] }))
  await page.route("**/api/v1/uploads", (route) => route.fulfill({ status: 201, json: { image_key: "sim-e2e-1-living-room.jpg" } }))
  await page.route("**/agent/brief", (route) =>
    route.fulfill({ status: 202, json: { run_id: photoJourney.id, status: "running", poll: `/agent/runs/${photoJourney.id}` } }),
  )
  await page.route("**/agent/runs/*", (route) => route.fulfill({ json: photoJourney }))
  await page.route("**/api/v1/simulations**", (route) => route.fulfill({ json: photographedRoom }))
})

test("a photo of the room is stored, then every candidate is fitted into the room it shows", async ({ page }) => {
  await page.goto("/room-simulator")
  await page.locator("#agent-photo").setInputFiles({ name: "living-room.jpg", mimeType: "image/jpeg", buffer: Buffer.from("\u00ff\u00d8\u00ff\u00e1") })
  await expect(page.getByText("living-room.jpg")).toBeVisible()

  const sent = page.waitForRequest("**/agent/brief")
  await page.getByRole("button", { name: /Find what fits/i }).click()

  expect((await sent).postDataJSON()).toMatchObject({ image_key: "sim-e2e-1-living-room.jpg" })
  await expect(page.getByText("Room measured from the photo").first()).toBeVisible()
})

test("the agent's recommendation is shown as a plan and as the room itself", async ({ page }) => {
  await page.goto("/room-simulator")
  await page.getByRole("button", { name: /Find what fits/i }).click()

  await expect(page.getByText("Room measured from your photo")).toBeVisible()
  const plan = page.getByRole("img", { name: /Room 3.6 by 3 metres/ })
  await expect(plan).toBeVisible()

  await page.getByRole("button", { name: /3D room/i }).click()
  await expect(plan).toHaveCount(0)
  const canvas = page.locator("canvas")
  await expect(canvas).toBeVisible()
  expect((await canvas.boundingBox())?.width).toBeGreaterThan(200)
})
