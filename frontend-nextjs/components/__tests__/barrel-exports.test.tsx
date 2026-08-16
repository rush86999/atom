import React from "react";
import { render } from "@testing-library/react";
import Document from "@/pages/_document";

jest.mock("next/document", () => {
  const React = require("react");
  return {
    Html: ({ children }: any) => React.createElement("html", { lang: "en" }, children),
    Head: () => React.createElement("head"),
    Main: () => React.createElement("main"),
    NextScript: () => React.createElement("script"),
  };
});

describe("barrel exports and _document", () => {
  it("renders the custom document shell", () => {
    const { container } = render(<Document />);
    expect(container.querySelector("html")).toBeInTheDocument();
    expect(container.querySelector("main")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeInTheDocument();
  });

  it("exposes all ui barrel modules", () => {
    const ui = require("@/components/ui/index");
    expect(ui.Card).toBeDefined();
    expect(ui.Button).toBeDefined();
    expect(ui.Input).toBeDefined();
    expect(ui.Label).toBeDefined();
    expect(ui.Textarea).toBeDefined();
    expect(ui.Tabs).toBeDefined();
    expect(ui.Badge).toBeDefined();
    expect(ui.Alert).toBeDefined();
    expect(ui.Select).toBeDefined();
  });

  it("exposes all dashboard barrel modules", () => {
    const dash = require("@/components/dashboard/index");
    expect(dash.AnalyticsDashboard).toBeDefined();
    expect(dash.MetricsCard).toBeDefined();
    expect(dash.DailyBriefingCard).toBeDefined();
    expect(dash.HealthMetricsGrid).toBeDefined();
  });

  it("exposes all debugging barrel modules", () => {
    const dbg = require("@/components/Debugging/index");
    expect(dbg.DebugPanel).toBeDefined();
    expect(dbg.BreakpointMarker).toBeDefined();
    expect(dbg.StepControls).toBeDefined();
    expect(dbg.VariableInspector).toBeDefined();
    expect(dbg.ExecutionTraceViewer).toBeDefined();
    expect(dbg.VariableModifier).toBeDefined();
    expect(dbg.SessionPersistence).toBeDefined();
    expect(dbg.PerformanceProfiler).toBeDefined();
    expect(dbg.CollaborativeDebugging).toBeDefined();
  });

  it("exposes all hubspot barrel modules", () => {
    const hs = require("@/components/integrations/hubspot/index");
    expect(hs.HubSpotIntegration).toBeDefined();
    expect(hs.HubSpotSearch).toBeDefined();
    expect(hs.HubSpotDashboard).toBeDefined();
    expect(hs.HubSpotAIService).toBeDefined();
    expect(hs.HubSpotWorkflowAutomation).toBeDefined();
    expect(hs.HubSpotPredictiveAnalytics).toBeDefined();
  });

  it("exposes all collaboration barrel modules", () => {
    const collab = require("@/components/Collaboration/index");
    expect(collab.UserPresenceList).toBeDefined();
    expect(collab.EditLockIndicator).toBeDefined();
    expect(collab.CollaborativeCursor).toBeDefined();
    expect(collab.ShareWorkflowModal).toBeDefined();
  });

  it("exposes all versioning barrel modules", () => {
    const ver = require("@/components/Versioning/index");
    expect(ver.VersionHistoryTimeline).toBeDefined();
    expect(ver.VersionDiffViewer).toBeDefined();
    expect(ver.RollbackWorkflowModal).toBeDefined();
    expect(ver.VersionComparisonMetrics).toBeDefined();
  });

  it("exposes all templates barrel modules", () => {
    const tmpl = require("@/components/Templates/index");
    expect(tmpl.TemplateEditor).toBeDefined();
    expect(tmpl.TemplateMetadataForm).toBeDefined();
    expect(tmpl.MyTemplatesPage).toBeDefined();
  });

  it("exposes the monday and layout barrel modules", () => {
    expect(require("@/components/integrations/monday/index").MondayIntegration).toBeDefined();
    expect(require("@/components/layout/index").Layout).toBeDefined();
  });
});
