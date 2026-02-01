import { test, expect } from "@playwright/test";

test.describe("Health Check Tests", () => {
  test("base URL responds", async ({ page }) => {
    const response = await page.goto(
      process.env.TEST_BASE_URL || "http://localhost:3000",
    );
    expect(response?.ok()).toBeTruthy();
  });

  test("basic app structure loads", async ({ page }) => {
    await page.goto(process.env.TEST_BASE_URL || "http://localhost:3000");

    // Check for basic app element presence
    const title = await page.title();
    expect(title).toBeTruthy();

    // Accept that it's a new system - check for any content
    const bodyText = await page.textContent("body");
    expect(bodyText).toBeTruthy();
  });

  test("environment is properly configured", async () => {
    // Verify critical env vars
    expect(process.env.TEST_BASE_URL).toBeDefined();
    console.log("✅ Environment seems configured");
  });
});
