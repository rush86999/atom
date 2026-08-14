/**
 * Dashboard router pages (were 0% coverage)
 *
 * Each page renders a Head block plus a single "Command Center" component.
 * The command centers are heavy, data-driven components and are mocked here;
 * the tests assert the page mounts the right command center.
 *
 * Covers: pages/dashboards/knowledge.tsx, projects.tsx, sales.tsx, support.tsx
 */

import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("@/components/dashboards/KnowledgeCommandCenter", () => ({
  __esModule: true,
  default: () => <div data-testid="knowledge-command-center" />,
}));
jest.mock("@/components/dashboards/ProjectCommandCenter", () => ({
  __esModule: true,
  default: () => <div data-testid="project-command-center" />,
}));
jest.mock("@/components/dashboards/SalesCommandCenter", () => ({
  __esModule: true,
  default: () => <div data-testid="sales-command-center" />,
}));
jest.mock("@/components/dashboards/SupportCommandCenter", () => ({
  __esModule: true,
  default: () => <div data-testid="support-command-center" />,
}));

import KnowledgeDashboard from "@/pages/dashboards/knowledge";
import ProjectsDashboard from "@/pages/dashboards/projects";
import SalesDashboard from "@/pages/dashboards/sales";
import SupportDashboard from "@/pages/dashboards/support";

// These pages rely on Next.js' automatic JSX runtime and do not import React.
// ts-jest is configured with jsx: "react" (see jest.config.js), which compiles
// their JSX to `React.createElement` — a free variable that only resolves via
// the global scope. Expose React globally for this test module so the pages
// render without touching the shared jest transform config.
(globalThis as any).React = React;

describe("dashboard router pages", () => {
  beforeEach(() => {
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  // [dashboard name, page component, command center testid]
  const dashboards: [string, React.FC, string][] = [
    ["knowledge", KnowledgeDashboard, "knowledge-command-center"],
    ["projects", ProjectsDashboard, "project-command-center"],
    ["sales", SalesDashboard, "sales-command-center"],
    ["support", SupportDashboard, "support-command-center"],
  ];

  test.each(dashboards)("%s dashboard renders its command center", (_name, Page, testid) => {
    const { container, unmount } = render(<Page />);
    expect(screen.getByTestId(testid)).toBeInTheDocument();
    // Background glow div is rendered alongside the command center
    expect(container.querySelector(".relative")).toBeInTheDocument();
    unmount();
  });
});
