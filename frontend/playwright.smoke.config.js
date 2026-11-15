import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/smoke",
  retries: 0,
  use: { ...devices["Desktop Chrome"], baseURL: process.env.FRONTEND_BASE_URL || "http://127.0.0.1:8080",
    trace: "retain-on-failure" },
});
