import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: true,
  workers: process.env.CI ? 2 : undefined,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:4173", trace: "retain-on-failure" },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" } },
  ],
  webServer: {
    command: "python3 server.py",
    env: { PORT: "4173", API_UPSTREAM: "http://127.0.0.1:1", OUTPUTS_FILE: "/not-provisioned/outputs.json" },
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 15000,
  },
});
