import fs from "node:fs";

import { expect, test } from "@playwright/test";

type GuidedDomain = {
  objective: string;
  scope: string;
  kind: string;
  recipient: string;
  expected: string;
  source: string;
};

test("guided objective discovers a real scoped catalog resource and survives reload", async ({
  page,
  context,
  request,
}) => {
  await context.addCookies([{
    name: "auth_token",
    value: "browser-acceptance-token",
    domain: "127.0.0.1",
    path: "/",
  }]);
  const health = await (await request.get(
    "http://127.0.0.1:8090/api/health",
  )).json();
  const domains: GuidedDomain[] = health.guided;
  await page.goto(`/assignments?agent=${encodeURIComponent(health.agent_id)}`);

  for (const domain of domains) {
    await page.getByLabel("Assignment objective").fill(domain.objective);
    await page.getByLabel("Discover resource from scope").check();
    await page.getByLabel("Permitted source scope").fill(domain.scope);
    await page.getByLabel("Deliverable kind").selectOption(domain.kind);
    if (domain.recipient) {
      await page.getByLabel("Test recipient").fill(domain.recipient);
    }
    await page.getByRole("button", { name: /Start assignment/ }).click();

    const detail = page.getByTestId("assignment-detail");
    await expect(detail).toBeVisible({ timeout: 15_000 });
    await expect(detail.getByText(domain.objective).first()).toBeVisible();
    if (domain.recipient) {
      await expect(detail.getByText(/Approval required/)).toBeVisible();
      await detail.getByRole("button", { name: /Approve this payload/ }).click();
    }
    await expect(detail.getByText("completed", { exact: true })).toBeVisible({
      timeout: 20_000,
    });

    const summaries = await (await request.get(
      "http://127.0.0.1:8090/api/assignments?include_terminal=true",
    )).json();
    const summary = summaries.find(
      (item: any) => item.assignment.objective === domain.objective,
    );
    expect(summary, `durable summary for ${domain.objective}`).toBeTruthy();
    const status = await (await request.get(
      `http://127.0.0.1:8090/api/assignments/${summary.run_id}`,
    )).json();
    expect(status.assignment.status).toBe("completed");
    const artifact = status.assignment.deliverables.find(
      (item: any) => item.artifact_path,
    );
    expect(artifact, `artifact for ${domain.objective}`).toBeTruthy();
    expect(fs.existsSync(artifact.artifact_path)).toBe(true);

    if (process.env.ATOM_BROWSER_EVIDENCE_DIR) {
      await page.screenshot({
        path: `${process.env.ATOM_BROWSER_EVIDENCE_DIR}/guided-${domain.kind}-completed.png`,
        fullPage: true,
      });
    }
  }

  const outbox = await (await request.get(
    "http://127.0.0.1:8090/api/health",
  )).json();
  if (outbox.outbox) {
    const lines = fs.readFileSync(outbox.outbox, "utf8").trim().split("\n");
    expect(lines.length).toBeGreaterThanOrEqual(1);
    expect(lines.join("\n")).toContain(domains[0].expected);
    expect(lines.join("\n")).toContain(domains[0].source);
  }

  await page.reload();
  for (const domain of domains) {
    await page
      .getByRole("button")
      .filter({ hasText: domain.objective })
      .first()
      .click();
    await expect(
      page.getByTestId("assignment-detail").getByText("completed", {
        exact: true,
      }),
    ).toBeVisible({ timeout: 15_000 });
  }
});
