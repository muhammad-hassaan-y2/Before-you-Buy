import { expect, test } from "@playwright/test"

import { catalog, simulation } from "./fixtures"

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/catalog", (route) => route.fulfill({ json: catalog }))
  await page.route("**/api/v1/simulations**", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({ status: 202, json: { id: simulation.id, status: "pending" } })
      : route.fulfill({ json: simulation }),
  )
})

test("a catalog piece is stood in the room at scale", async ({ page }) => {
  await page.goto("/workspace")
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("3D workspace")

  await page.getByRole("button", { name: /KURA three-seat sofa/ }).click()
  await page.getByRole("button", { name: /Place it in 3D/i }).click()

  await expect(page.getByText("KURA three-seat sofa", { exact: true }).first()).toBeVisible()
  const canvas = page.locator("canvas")
  await expect(canvas).toBeVisible()
  expect((await canvas.boundingBox())?.width).toBeGreaterThan(200)
  await expect(page.getByText(/could not open WebGL/i)).toHaveCount(0)
})

test("the scene offers the viewpoints the pipeline chose", async ({ page }) => {
  await page.goto("/workspace")
  await page.getByRole("button", { name: /KURA three-seat sofa/ }).click()
  await page.getByRole("button", { name: /Place it in 3D/i }).click()

  await expect(page.getByRole("button", { name: "overview" })).toBeVisible()
  await expect(page.getByRole("button", { name: "first-person" })).toBeVisible()
  await page.getByRole("button", { name: "first-person" }).click()
  await expect(page.getByRole("button", { name: "Reset view" })).toBeVisible()
})

test("placing it somewhere that does not fit is shown as such", async ({ page }) => {
  await page.goto("/workspace")
  await page.getByRole("button", { name: /KURA three-seat sofa/ }).click()
  await page.getByRole("button", { name: /Place it in 3D/i }).click()

  await expect(page.getByText("against the long wall")).toBeVisible()
  await page.getByRole("button", { name: "by the window" }).click()
  await expect(page.getByText("walkways at by the window")).toBeVisible()
  await expect(page.getByText("floor used 14.2 %")).toBeVisible()
})

test("the measured plan stays under the 3D view", async ({ page }) => {
  await page.goto("/workspace")
  await page.getByRole("button", { name: /KURA three-seat sofa/ }).click()
  await page.getByRole("button", { name: /Place it in 3D/i }).click()

  await expect(page.getByText("14.0 m² room")).toBeVisible()
  await expect(page.getByText("13.6 m² usable")).toBeVisible()
  await expect(page.locator("svg").first()).toBeVisible()
})

test("the verdict carries the delivery path the engine checked", async ({ page }) => {
  await page.goto("/workspace")
  await page.getByRole("button", { name: /KURA three-seat sofa/ }).click()
  await page.getByRole("button", { name: /Place it in 3D/i }).click()

  await expect(page.getByText("doorway is tight")).toBeVisible()
  await expect(page.getByText("fragile by 2 cm")).toBeVisible()
  await expect(page.getByText(/reality is off by 2 cm/)).toBeVisible()
  await expect(page.getByText("Measure the doorway as well as the room: the box is inside 2 cm of the frame.")).toBeVisible()
})
