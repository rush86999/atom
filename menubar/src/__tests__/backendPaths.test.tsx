import { render, waitFor } from "@testing-library/react";
import AnalyticsPanel from "../components/AnalyticsPanel";
import ApprovalsPanel from "../components/ApprovalsPanel";
import IntegrationsPanel from "../components/IntegrationsPanel";
import WorkflowsPanel from "../components/WorkflowsPanel";

const LOOPBACK = "http://127.0.0.1:8123";

function mockJson(body: unknown): jest.Mock {
  return jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
  });
}

function requestedUrls(): string[] {
  return (globalThis.fetch as jest.Mock).mock.calls.map((call: unknown[]) =>
    String(call[0])
  );
}

async function expectRequested(suffix: string): Promise<void> {
  await waitFor(() => {
    expect(
      requestedUrls().some((url) => url.startsWith(`${LOOPBACK}${suffix}`))
    ).toBe(true);
  });
  expect(requestedUrls().every((url) => !url.includes("localhost:8000"))).toBe(
    true
  );
}

describe("frontend backend paths", () => {
  test("approvals uses the loopback override", async () => {
    globalThis.fetch = mockJson({ pending_approvals: [] }) as unknown as typeof fetch;
    render(<ApprovalsPanel serverUrl={LOOPBACK} token="test-token" />);
    await expectRequested("/api/agent-governance/pending-approvals");
  });

  test("workflows uses the loopback override", async () => {
    globalThis.fetch = mockJson([]) as unknown as typeof fetch;
    render(<WorkflowsPanel serverUrl={LOOPBACK} token="test-token" />);
    await expectRequested("/api/mobile/workflows");
  });

  test("analytics uses the loopback override", async () => {
    globalThis.fetch = mockJson({
      total_executions: 0,
      successful_executions: 0,
      failed_executions: 0,
      success_rate: 0,
    }) as unknown as typeof fetch;
    render(<AnalyticsPanel serverUrl={LOOPBACK} token="test-token" />);
    await expectRequested("/api/analytics/dashboard/kpis?time_window=24h");
  });

  test("integrations uses the loopback override", async () => {
    globalThis.fetch = mockJson({
      total_integrations: 0,
      healthy_integrations: 0,
      integration_status: [],
    }) as unknown as typeof fetch;
    render(<IntegrationsPanel serverUrl={LOOPBACK} token="test-token" />);
    await expectRequested("/api/v1/integrations/health");
  });
});
