import { expect, test } from "@playwright/test"

import { catalog, cart, catalogFits, measuredCart, order } from "./fixtures"

/** The bag a shopper fills in the shop is the bag an agent fills in ChatGPT: the same
 *  `/agent/tools/*` doors, the same refusal of a yes nobody said. */
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/catalog**", (route) => route.fulfill({ json: catalog }))
  await page.route("**/agent/tools/fit_catalog", (route) => route.fulfill({ json: catalogFits }))
  await page.route("**/agent/tools/add_to_cart", (route) => route.fulfill({ json: { tool: "add_to_cart", result: cart } }))
  await page.route("**/agent/tools/view_cart", (route) => route.fulfill({ json: { tool: "view_cart", result: measuredCart } }))
  await page.route("**/agent/tools/measure_cart", (route) => route.fulfill({ json: { tool: "measure_cart", result: measuredCart } }))
  await page.route("**/agent/tools/checkout", (route) => route.fulfill({ json: { tool: "checkout", result: order } }))
})

test("a card bags the piece with the verdict the sweep already has", async ({ page }) => {
  await page.goto("/store")
  await page.getByRole("button", { name: /Measure in my room/ }).click()
  await expect(page.getByText("Fits")).toBeVisible()

  const sent = page.waitForRequest("**/agent/tools/add_to_cart")
  await page.getByRole("button", { name: "Add to bag" }).first().click()
  expect((await sent).postDataJSON()).toMatchObject({ sku: "BYB-KURA-3S", simulation_id: "sim-e2e-1", room_width_m: 4 })

  await expect(page.getByRole("dialog", { name: "Your bag" })).toBeVisible()
  await expect(page.getByRole("dialog", { name: "Your bag" }).getByText("KURA three-seat sofa")).toBeVisible()
})

test("the bag prices itself from the service, then judges the set", async ({ page }) => {
  await page.goto("/store")
  await page.getByRole("button", { name: /Measure in my room/ }).click()
  await page.getByRole("button", { name: "Add to bag" }).first().click()

  const dialog = page.getByRole("dialog", { name: "Your bag" })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText("€919").first()).toBeVisible()

  const measured = page.waitForRequest("**/agent/tools/measure_cart")
  await dialog.getByRole("button", { name: /Re-measure the bag/ }).click()
  expect((await measured).postDataJSON()).toMatchObject({ cart_id: "cart-e2e-1", room_width_m: 4 })

  await expect(dialog.getByText("€1,318", { exact: true })).toBeVisible()
  await expect(dialog.getByText("Bought together")).toBeVisible()
  await expect(dialog.getByText(/tightest walkway would be 0.6 m/)).toBeVisible()
})

test("ordering takes the shopper's own words, and nothing writes the draft without them", async ({ page }) => {
  await page.goto("/store")
  await page.getByRole("button", { name: /Measure in my room/ }).click()
  await page.getByRole("button", { name: "Add to bag" }).first().click()

  const place = page.getByRole("button", { name: /Place the order/ })
  await expect(place).toBeDisabled()

  const notSent = page.waitForRequest("**/agent/tools/checkout", { timeout: 1500 }).then(() => "sent").catch(() => "not sent")
  await place.click({ force: true }).catch(() => undefined)
  expect(await notSent).toBe("not sent")

  await page.getByLabel("Your own words").fill("yes, order both of them")
  await expect(place).toBeEnabled()
  const sent = page.waitForRequest("**/agent/tools/checkout")
  await place.click()
  expect((await sent).postDataJSON()).toMatchObject({ cart_id: "cart-e2e-1", confirmation: "yes, order both of them" })

  await expect(page.getByText(/Draft placed/)).toBeVisible()
  await expect(page.getByText(/A person at the shop accepts or releases this draft/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Open your bag, 2 pieces" })).toBeVisible()
})

test("a piece the engine refused does not reach the bag", async ({ page }) => {
  await page.goto("/store")
  await page.getByRole("button", { name: /Measure in my room/ }).click()

  const blocked = page.getByRole("button", { name: "Not for this room" })
  await expect(blocked).toBeVisible()
  await expect(blocked).toBeDisabled()
})
