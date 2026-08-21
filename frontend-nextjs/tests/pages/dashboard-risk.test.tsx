/**
 * Round 80 — Risk Control Center consumes the REAL risk endpoints
 * (/api/risk/customer-protection, /fraud, /early-warning) which are
 * auth-gated. Previously the page called /api/risk/{churn,financial,growth}
 * — paths that exist nowhere in the backend — so the whole page rendered
 * empty. Growth-readiness has no data source at all and was removed.
 */
import React from "react";
import { renderWithProviders, screen, waitFor } from "../../tests/test-utils";

jest.mock("@/components/desktop/DesktopSecurityAudit", () => ({
  DesktopSecurityAudit: () => <div data-testid="security-audit-stub" />,
}));

import RiskDashboard from "@/pages/dashboard/risk";

const realFetch = global.fetch;

const authSeen: string[] = [];

function jsonResponse(body: any, status = 200) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

beforeEach(() => {
  jest.spyOn(console, "error").mockImplementation(() => {});
  window.localStorage.setItem("auth_token", "jwt-risk-token");
  authSeen.length = 0;
  global.fetch = jest.fn(((url: any) => {
    const u = String(url);
    const optsAuth = "n/a"; // headers asserted via calls below where present
    if (u.includes("/api/risk/customer-protection")) {
      authSeen.push(u);
      return Promise.resolve(
        jsonResponse({
          churn_risk: [
            { deal_id: "d1", client_name: "Acme Corp", value: 15000, days_silent: 45, risk_level: "HIGH" },
            { deal_id: "d2", client_name: "Globex", value: 5000, days_silent: 12, risk_level: "LOW" },
          ],
          vip_opportunities: [],
          is_mock: true,
        })
      );
    }
    if (u.includes("/api/risk/fraud")) {
      authSeen.push(u);
      return Promise.resolve(
        jsonResponse({
          anomalies: [
            { id: "tx-999", type: "LARGE_OUTFLOW", description: "Unusual refund to unknown entity", amount: 4500, severity: "HIGH", date: "2026-01-05" },
          ],
        })
      );
    }
    if (u.includes("/api/risk/early-warning")) {
      authSeen.push(u);
      return Promise.resolve(
        jsonResponse({
          ar_alerts: [
            { id: "inv-001", description: "Consulting Services Q3", amount: 12500, days_overdue: 52 },
          ],
        })
      );
    }
    return Promise.resolve(jsonResponse({}, 404));
  }) as any);
});

afterEach(() => {
  global.fetch = realFetch;
  window.localStorage.clear();
});

test("renders churn, fraud and AR data from the real risk endpoints", async () => {
  renderWithProviders(<RiskDashboard />);

  // churn rows come from /customer-protection
  await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());
  expect(screen.getByText("Globex")).toBeInTheDocument();
  expect(screen.getByText(/Unusual refund to unknown entity/i)).toBeInTheDocument();
  expect(screen.getByText(/Consulting Services Q3/i)).toBeInTheDocument();

  // every risk call carried the stored JWT (endpoints are auth-gated);
  // StrictMode may double-invoke the effect, so assert the invariant
  const riskCalls = (global.fetch as jest.Mock).mock.calls.filter(
    ([u]: any[]) => String(u).includes("/api/risk/")
  );
  expect(riskCalls.length).toBeGreaterThanOrEqual(3);
  expect(
    riskCalls.every(([, opts]: any[]) => opts?.headers?.Authorization === "Bearer jwt-risk-token")
  ).toBe(true);
});

test("no longer calls the phantom /churn, /financial, /growth paths", async () => {
  renderWithProviders(<RiskDashboard />);
  await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());
  const urls = (global.fetch as jest.Mock).mock.calls.map(([u]: any) => String(u));
  expect(urls.some((u) => u.includes("/api/risk/churn"))).toBe(false);
  expect(urls.some((u) => u.includes("/api/risk/financial"))).toBe(false);
  expect(urls.some((u) => u.includes("/api/risk/growth"))).toBe(false);
});
