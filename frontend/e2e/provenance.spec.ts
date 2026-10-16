import { expect, test, type Page } from "@playwright/test"

import { simulation } from "./fixtures"

/** The simulator card reads whatever the workers stored, so each case is one stored profile. */
async function simulateWith(page: Page, profile: Record<string, unknown>) {
  await page.route("**/api/v1/simulations**", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({ status: 202, json: { id: simulation.id, status: "pending" } })
      : route.fulfill({ json: { ...simulation, product_profile: { ...simulation.product_profile, ...profile } } }),
  )
  await page.goto("/room-simulator")
  await page.getByLabel("Product link").fill("https://example.com/sofa")
  await page.getByRole("button", { name: /Simulate in my room/i }).click()
}

test("a Token Factory read is named as the AMD model that did it", async ({ page }) => {
  await simulateWith(page, {
    source: "amd_token_factory",
    provider: "amd_token_factory",
    model: "example-model-id",
    confidence: 0.72,
    dimension_reliability: { width_cm: "extracted", depth_cm: "extracted", height_cm: "extracted" },
    measurement_basis: "amd_token_factory",
  })

  await expect(page.getByText("AMD Token Factory", { exact: true })).toBeVisible()
  await expect(page.getByText(/category guess|None of these sizes/)).toHaveCount(0)
})

test("a catalog SKU is never warned about as a guess", async ({ page }) => {
  await simulateWith(page, {})
  await expect(page.getByText("Catalog SKU", { exact: true })).toBeVisible()
  await expect(page.getByText(/category guess|None of these sizes/)).toHaveCount(0)
})

test("a partly readable listing says which size was guessed", async ({ page }) => {
  await simulateWith(page, {
    source: "heuristic",
    confidence: 0.35,
    dimension_reliability: { width_cm: "verified", depth_cm: "verified", height_cm: "estimated" },
    measurement_basis: "listing_partial",
  })

  await expect(page.getByText(/height is a category guess/)).toBeVisible()
  // The dimensions badge and the warning both spell the box out.
  await expect(page.getByText("200 × 90 × 84 cm").first()).toBeVisible()
})

test("a category default for the whole box is called out", async ({ page }) => {
  await simulateWith(page, {
    source: "heuristic",
    confidence: 0.25,
    dimension_reliability: { width_cm: "estimated", depth_cm: "estimated", height_cm: "estimated" },
    measurement_basis: "category_estimate",
  })

  await expect(page.getByText(/None of these sizes came from the listing/)).toBeVisible()
})
