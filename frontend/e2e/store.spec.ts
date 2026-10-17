import { expect, test } from "@playwright/test"

import { catalog, catalogFits, simulation } from "./fixtures"

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/catalog**", (route) =>
    route.fulfill({ json: route.request().url().endsWith("/catalog") ? catalog : catalog[0] }),
  )
  await page.route("**/agent/tools/fit_catalog", (route) => route.fulfill({ json: catalogFits }))
  await page.route("**/api/v1/simulations**", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({ status: 202, json: { id: simulation.id, status: "pending" } })
      : route.fulfill({ json: simulation }),
  )
})

test("the shelf quotes terms the catalog actually computes", async ({ page }) => {
  await page.goto("/store")

  await expect(page.getByRole("heading", { level: 1 })).toContainText("answers before you add to cart")
  await expect(page.getByText("€919")).toBeVisible()
  await expect(page.getByText("€399")).toBeVisible()
  await expect(page.getByText("18 days · pallet freight")).toBeVisible()
  await expect(page.getByText("Porto Frame Works · PT").first()).toBeVisible()
  // Nothing is presented as fitting until the geometry worker says so.
  await expect(page.getByText("Not measured")).toHaveCount(2)
})

test("measuring the room puts a verdict on the cards it settled", async ({ page }) => {
  await page.goto("/store")
  await expect(page.getByRole("link", { name: /KURA three-seat sofa/ })).toBeVisible()

  const sent = page.waitForRequest("**/agent/tools/fit_catalog")
  await page.getByRole("button", { name: /Measure in my room/ }).click()
  expect((await sent).postDataJSON()).toMatchObject({ room_width_m: 4, room_depth_m: 3.5, limit: 8 })

  await expect(page.getByText("Fits")).toBeVisible()
  await expect(page.getByText("Too large")).toBeVisible()
  await expect(page.getByText(/pieces measured in a 4 × 3.5 m room/)).toBeVisible()
})

test("a listing tests itself in the shopper's room by pasting its own URL", async ({ page }) => {
  await page.goto("/product/BYB-KURA-3S")

  await expect(page.getByRole("heading", { level: 1 })).toHaveText("KURA three-seat sofa")
  await expect(page.getByText("€919")).toBeVisible()
  await expect(page.getByText("€404 · 44.0%")).toBeVisible()
  await expect(page.getByText(/no supplier feed connected/)).toBeVisible()

  const sent = page.waitForRequest("**/api/v1/simulations")
  await page.getByRole("button", { name: /Simulate in my room/ }).click()
  const form = (await sent).postData()
  expect(form).toContain(catalog[0].commerce.product_url)

  await expect(page.getByText("Fits with room to move")).toBeVisible()
  await expect(page.getByRole("img", { name: /Room 4 by 3.5 metres/ })).toBeVisible()
})

test("an unknown SKU says so instead of showing an empty shelf", async ({ page }) => {
  await page.route("**/api/v1/catalog/BYB-NOTHING", (route) => route.fulfill({ status: 404, json: { detail: "no SKU BYB-NOTHING" } }))
  await page.goto("/product/BYB-NOTHING")

  await expect(page.getByText(/no SKU BYB-NOTHING/)).toBeVisible()
  await expect(page.getByRole("button", { name: /Simulate in my room/ })).toHaveCount(0)
})

test("the shop is the front door, and the agent is one click away", async ({ page }) => {
  await page.goto("/")
  await expect(page).toHaveURL(/\/store$/)
  await expect(page.getByRole("link", { name: "Shop", exact: true })).toBeVisible()

  await page.getByRole("link", { name: "Fit agent" }).click()
  await expect(page.getByRole("heading", { level: 1, name: "The fit agent" })).toBeVisible()
})
