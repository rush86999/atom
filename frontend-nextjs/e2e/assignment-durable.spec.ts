import { expect, test } from "@playwright/test";

const DOMAINS = [
  { objective: "Browser commercial response", correlation: "browser-A" },
  { objective: "Browser eligibility package", correlation: "browser-B" },
];

test("durable assignment UI completes both domains and survives reload", async ({ page, context }) => {
  await context.addCookies([{
    name: "auth_token",
    value: "browser-acceptance-token",
    domain: "127.0.0.1",
    path: "/",
  }]);
  await page.goto("/assignments");
  for (const domain of DOMAINS) {
    await expect(page.getByText(domain.objective).first()).toBeVisible();
    await page
      .getByRole("button")
      .filter({ hasText: domain.objective })
      .first()
      .click();

    const detail = page.getByTestId("assignment-detail");
    await expect(detail).toBeVisible();
    await expect(detail.getByText(/Correlated response/)).toBeVisible();
    await detail.getByLabel("Correlated response").fill(
      `authorized reply for ${domain.correlation}`,
    );
    await detail.getByRole("button", { name: /Deliver/ }).click();

    await expect(detail.getByText(/Approval required/)).toBeVisible();
    await expect(detail.getByText(/Payload/)).toBeVisible();
    await detail.getByRole("button", { name: /Approve this payload/ }).click();

    await expect(detail.getByText("completed", { exact: true })).toBeVisible({
      timeout: 15_000,
    });
    await expect(detail.getByText(domain.objective)).toBeVisible();
    if (process.env.ATOM_BROWSER_EVIDENCE_DIR) {
      await page.screenshot({
        path: `${process.env.ATOM_BROWSER_EVIDENCE_DIR}/${domain.correlation}-completed.png`,
        fullPage: true,
      });
    }

    // Reopen: the same durable state is read, not reconstructed.
    await page.reload();
    await page
      .getByRole("button")
      .filter({ hasText: domain.objective })
      .first()
      .click();
    await expect(
      page.getByTestId("assignment-detail").getByText("completed", {
        exact: true,
      }),
    ).toBeVisible();
  }
});
