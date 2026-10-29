import { expect, test } from "@playwright/test";

const DOMAINS = [
  {
    objective: "Browser commercial response",
    sourceKey: "workbook",
    outputKey: "commercial_output",
    kind: "document",
    expression: "2*10 + 3*20",
    content:
      "## Summary\n\nTotal ${calculate.value}\n\n## Sources\n\n- connected-records.xlsx (Records)",
    recipient: "test-recipient@example.invalid",
    correlation: "browser-A",
  },
  {
    objective: "Browser eligibility package",
    sourceKey: "document",
    outputKey: "eligibility_output",
    kind: "presentation",
    expression: "",
    content:
      "Slide 1: Overview\n- record-2\n\nSlide 2: Findings\n- Subject: record-2\n- Status: active\n\nSlide 3: Sources\n- qualification.txt",
    recipient: "",
    correlation: "",
  },
];

test("user starts both domains from the product and reload keeps durable state", async ({ page, context, request }) => {
  await context.addCookies([{
    name: "auth_token",
    value: "browser-acceptance-token",
    domain: "127.0.0.1",
    path: "/",
  }]);
  const health = await (await request.get(
    "http://127.0.0.1:8090/api/health",
  )).json();
  await page.goto(`/assignments?agent=${encodeURIComponent(health.agent_id)}`);

  for (const domain of DOMAINS) {
    await page.getByLabel("Assignment objective").fill(domain.objective);
    await page.getByLabel("Authorized source path").fill(health[domain.sourceKey]);
    await page.getByLabel("Deliverable kind").selectOption(domain.kind);
    await page.getByLabel("Artifact content").fill(domain.content);
    if (domain.expression) {
      await page.getByLabel("Calculation expression").fill(domain.expression);
    }
    if (domain.recipient) {
      await page.getByLabel("Test recipient").fill(domain.recipient);
    }
    if (domain.correlation) {
      await page.getByLabel("Correlation id").fill(domain.correlation);
    }
    await page.getByRole("button", { name: /Start assignment/ }).click();

    const detail = page.getByTestId("assignment-detail");
    await expect(detail).toBeVisible({ timeout: 15_000 });
    await expect(detail.getByText(domain.objective).first()).toBeVisible();

    if (domain.correlation) {
      await expect(detail.getByText(/Correlated response/)).toBeVisible();
      await detail.getByLabel("Correlated response").fill(
        "authorized external fact",
      );
      await detail.getByRole("button", { name: /Deliver/ }).click();
    }
    if (domain.recipient) {
      await expect(detail.getByText(/Approval required/)).toBeVisible();
      await expect(detail.getByText(/Payload/)).toBeVisible();
      await detail.getByRole("button", { name: /Approve this payload/ }).click();
    }
    await expect(detail.getByText("completed", { exact: true })).toBeVisible({
      timeout: 15_000,
    });
    if (process.env.ATOM_BROWSER_EVIDENCE_DIR) {
      await page.screenshot({
        path: `${process.env.ATOM_BROWSER_EVIDENCE_DIR}/${domain.kind}-completed.png`,
        fullPage: true,
      });
    }
  }

  await page.reload();
  for (const domain of DOMAINS) {
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
