import { expect, test } from "@playwright/test"

import { estimate, journey, reservations, tools } from "./fixtures"

test.beforeEach(async ({ page }) => {
  await page.route("**/agent/tools", (route) => route.fulfill({ json: tools }))
  await page.route("**/agent/reservations**", (route) => route.fulfill({ json: reservations }))
  await page.route("**/agent/tools/returns_estimate", (route) => route.fulfill({ json: estimate }))
  await page.route("**/agent/brief", (route) => route.fulfill({ status: 202, json: { run_id: journey.id, status: "running", poll: `/agent/runs/${journey.id}` } }))
  await page.route("**/agent/runs/*", (route) => route.fulfill({ json: journey }))
  await page.route("**/agent/chat", (route) => route.fulfill({ json: { answer: "Yes - 0.60 m in front of it.", answered_by: "evolus", conversation_id: "c-1" } }))
})

test("the agent shows the journey, not only the answer", async ({ page }) => {
  await page.goto("/room-simulator")
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("The fit agent")

  await page.getByLabel("Your brief").fill("three-seater sofa under 900")
  await page.getByRole("button", { name: /Find what fits/i }).click()

  await expect(page.getByText("Catalog shortlisted")).toBeVisible()
  await expect(page.getByText("POST /v1/chat/completions")).toBeVisible()
  await expect(page.getByText("Pass 2")).toBeVisible()
  await expect(page.getByText("The KURA three-seat sofa fits your room with 0.60 m left to walk in front of it.")).toBeVisible()
})

test("each tested piece carries the geometry that decided it", async ({ page }) => {
  await page.goto("/room-simulator")
  await page.getByRole("button", { name: /Find what fits/i }).click()

  // The name is also on the merchant's hold list below, so check the row the agent tested.
  await expect(page.getByText("KURA three-seat sofa", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("0.20 m walkway")).toBeVisible()
  await expect(page.getByText("recommend", { exact: true })).toBeVisible()
  await expect(page.getByText("widest walkway of the four tested pieces")).toBeVisible()
})

test("the shortlist is honest about a widened budget", async ({ page }) => {
  await page.goto("/room-simulator")
  await page.getByRole("button", { name: /Find what fits/i }).click()

  await expect(page.getByText("no candidate cleared the walkway, widening the band")).toBeVisible()
  await expect(page.getByText("pass-1 · parallel").first()).toBeVisible()
})

test("the chat panel threads a conversation and says which brain replied", async ({ page }) => {
  await page.goto("/room-simulator")
  await page.getByRole("button", { name: /Will a 220 cm sofa fit/i }).click()

  await expect(page.getByText("Yes - 0.60 m in front of it.")).toBeVisible()
  await expect(page.getByText("Evolus agent", { exact: true })).toBeVisible()

  await page.getByLabel(/Ask about a piece/i).fill("and the door?")
  await page.getByRole("button", { name: "Send" }).click()
  await expect(page.getByText("and the door?")).toBeVisible()
})

test("the capability surface advertises the MCP door", async ({ page }) => {
  await page.goto("/room-simulator")
  await expect(page.getByText("start_journey")).toBeVisible()
  await expect(page.getByText(/\/mcp\/$/)).toBeVisible()
})

test("no Evolus widget is loaded while the workspace is unconfigured", async ({ page }) => {
  await page.goto("/room-simulator")
  await expect(page.locator("script[src*='evolus']")).toHaveCount(0)
})

test("the trace totals what the journey spent, and where the time went", async ({ page }) => {
  await page.goto("/room-simulator")
  await page.getByRole("button", { name: /Find what fits/i }).click()

  await expect(page.getByText("6.7 s measured")).toBeVisible()
  await expect(page.getByText("1 fit by the geometry worker")).toBeVisible()
  await expect(page.getByText("3 model calls")).toBeVisible()
  await expect(page.getByText("2 search passes")).toBeVisible()
  await expect(page.getByText("evolus exec-e2e-1")).toBeVisible()
})

test("the merchant's number is the service's arithmetic, not the browser's", async ({ page }) => {
  await page.goto("/room-simulator")
  await page.getByLabel("Orders / month").fill("1000")
  await page.getByRole("button", { name: "Recalculate" }).click()

  await expect(page.getByText("€ 25125")).toBeVisible()
  await expect(page.getByText("33.5")).toBeVisible()
  await expect(page.getByText(/200 returns, 134 of them because it did not fit/)).toBeVisible()
})

test("a hold only appears because a shopper said yes in their own words", async ({ page }) => {
  await page.goto("/room-simulator")

  await expect(page.getByText("yes, hold the KURA for me")).toBeVisible()
  await expect(page.getByText("pending merchant")).toBeVisible()
  await expect(page.getByRole("link", { name: /fit evidence/ })).toHaveAttribute("href", "/api/v1/simulations/sim-e2e-1")
})
