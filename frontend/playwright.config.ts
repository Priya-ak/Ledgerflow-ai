import { defineConfig, devices } from "@playwright/test";

// Expects backend (http://127.0.0.1:8000, freshly seeded demo data) and frontend
// (http://localhost:3000) to be running. See docs/testing-guide.md.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  workers: 1, // one browser at a time keeps memory low on 4 GB machines
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
