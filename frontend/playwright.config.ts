import { defineConfig, devices } from "@playwright/test"

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173"

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI
    ? [
        ["github"],
        ["html", { open: "never", outputFolder: "playwright-report" }],
      ]
    : "html",
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: process.env.CI ? "on" : "retain-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /e2e\.setup\.ts/ },
    {
      name: "admin-desktop",
      testMatch: /admin\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/admin.json",
      },
      dependencies: ["setup"],
    },
    {
      name: "operator-desktop",
      testMatch: /operator\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/operator.json",
      },
      dependencies: ["setup"],
    },
    {
      name: "viewer-desktop",
      testMatch: /viewer\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/viewer.json",
      },
      dependencies: ["setup"],
    },
    {
      name: "operator-mobile",
      testMatch: /mobile\.spec\.ts/,
      use: {
        ...devices["Pixel 7"],
        storageState: "playwright/.auth/operator.json",
      },
      dependencies: ["setup"],
    },
  ],
})
