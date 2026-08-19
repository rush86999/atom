import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  workers: 1, // sequential: shared single-tenant backend
  reporter: [["list"]],
  use: {
    baseURL: process.env.SMOKE_BASE_URL || "http://localhost:3001",
    headless: true,
  },
});
