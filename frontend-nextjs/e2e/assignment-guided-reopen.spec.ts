import fs from "node:fs";

import { expect, test } from "@playwright/test";

test("guided connected assignments survive a backend restart", async ({
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
  const summaries = await (await request.get(
    "http://127.0.0.1:8090/api/assignments?include_terminal=true",
  )).json();
  await page.goto("/assignments");
  for (const domain of health.guided) {
    await page
      .getByRole("button")
      .filter({ hasText: domain.objective })
      .first()
      .click();
    const detail = page.getByTestId("assignment-detail");
    await expect(detail.getByText("completed", { exact: true })).toBeVisible();
    const summary = summaries.find(
      (item: any) => item.assignment.objective === domain.objective,
    );
    expect(summary, `durable summary for ${domain.objective}`).toBeTruthy();
    const status = await (await request.get(
      `http://127.0.0.1:8090/api/assignments/${summary.run_id}`,
    )).json();
    const artifact = status.assignment.deliverables.find(
      (item: any) => item.artifact_path,
    );
    expect(artifact, `artifact for ${domain.objective}`).toBeTruthy();
    expect(fs.existsSync(artifact.artifact_path)).toBe(true);
  }
});
