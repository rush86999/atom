import { expect, test } from "@playwright/test";

const OBJECTIVES = [
  "Browser commercial response",
  "Browser eligibility package",
];

test("completed assignments survive a backend restart", async ({ page, context }) => {
  await context.addCookies([{
    name: "auth_token",
    value: "browser-acceptance-token",
    domain: "127.0.0.1",
    path: "/",
  }]);
  await page.goto("/assignments");
  for (const objective of OBJECTIVES) {
    await page
      .getByRole("button")
      .filter({ hasText: objective })
      .first()
      .click();
    await expect(
      page.getByTestId("assignment-detail").getByText("completed", {
        exact: true,
      }),
    ).toBeVisible();
  }
});
