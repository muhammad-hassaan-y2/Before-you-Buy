import { defineConfig, devices } from "@playwright/test"

const base = process.env.E2E_BASE_URL ?? "http://localhost:3000"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: { baseURL: base, trace: "on-first-retry" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // E2E_BASE_URL points at a stack that is already up (the docker compose frontend, say).
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : { command: "pnpm dev", url: base, reuseExistingServer: !process.env.CI, timeout: 180_000 },
})
