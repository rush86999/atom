/**
 * AuditTrailPage tests (pages/audit-trail/index.tsx)
 *
 * Covers: rendering the page shell with the audit trail explorer.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import AuditTrailPage from "@/pages/audit-trail";

jest.mock("@/components/Audit/AuditTrailExplorer", () => ({
  __esModule: true,
  default: () => <div data-testid="audit-trail-explorer">Audit</div>,
}));

describe("AuditTrailPage", () => {
  test("renders the audit trail explorer", () => {
    render(<AuditTrailPage />);
    expect(screen.getByTestId("audit-trail-explorer")).toBeInTheDocument();
  });
});
