/**
 * AutomationsPage tests (pages/automations.tsx, was 0% coverage)
 *
 * Covers: header + tab navigation, per-tab child panels, the
 * New Automation trigger counter, template selection (sessionStorage +
 * tab switch), agent generator callbacks (generated/deployed), and the
 * schedule link.
 */

import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import AutomationsPage from "@/pages/automations";

let latestWorkflowProps: any = null;
jest.mock("@/components/WorkflowAutomation", () => ({
  __esModule: true,
  default: (props: any) => {
    latestWorkflowProps = props;
    return <div data-testid="workflow-automation">Flows</div>;
  },
}));

let latestGalleryProps: any = null;
jest.mock("@/components/Automations/TemplateGallery", () => ({
  __esModule: true,
  default: (props: any) => {
    latestGalleryProps = props;
    return <div data-testid="template-gallery">Templates</div>;
  },
}));

let latestTablesProps: any = null;
jest.mock("@/components/Automations/WorkflowTables", () => ({
  __esModule: true,
  default: (props: any) => {
    latestTablesProps = props;
    return <div data-testid="workflow-tables">Tables</div>;
  },
}));

let latestVersioningProps: any = null;
jest.mock("@/components/Automations/FlowVersioning", () => ({
  __esModule: true,
  default: (props: any) => {
    latestVersioningProps = props;
    return <div data-testid="flow-versioning">Versions</div>;
  },
}));

let latestGeneratorProps: any = null;
jest.mock("@/components/Automations/AgentWorkflowGenerator", () => ({
  __esModule: true,
  default: (props: any) => {
    latestGeneratorProps = props;
    return <div data-testid="agent-generator">Agents</div>;
  },
}));

describe("AutomationsPage", () => {
  let consoleLogSpy: jest.SpyInstance;
  let setItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    latestWorkflowProps = null;
    latestGalleryProps = null;
    latestTablesProps = null;
    latestVersioningProps = null;
    latestGeneratorProps = null;
    consoleLogSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    setItemSpy = jest.spyOn(Storage.prototype, "setItem");
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
  });

  test("renders header, schedule link, and all tab buttons", () => {
    render(<AutomationsPage />);
    expect(screen.getByText("Automations")).toBeInTheDocument();
    expect(screen.getByText(/Build workflows with AI/)).toBeInTheDocument();
    expect(screen.getByText("Schedule").closest("a")?.getAttribute("href")).toBe(
      "/workflows/schedule"
    );
    expect(screen.getByRole("button", { name: /New Automation/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Flows/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AI Agents/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Templates/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tables/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Versions/ })).toBeInTheDocument();
  });

  test("defaults to the flows tab and switches through every tab", () => {
    render(<AutomationsPage />);
    expect(screen.getByTestId("workflow-automation")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /AI Agents/ }));
    expect(screen.getByTestId("agent-generator")).toBeInTheDocument();
    expect(screen.queryByTestId("workflow-automation")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Templates/ }));
    expect(screen.getByTestId("template-gallery")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Tables/ }));
    expect(screen.getByTestId("workflow-tables")).toBeInTheDocument();
    expect(latestTablesProps.className).toBe("h-[calc(100vh-120px)]");

    fireEvent.click(screen.getByRole("button", { name: /Versions/ }));
    expect(screen.getByTestId("flow-versioning")).toBeInTheDocument();
    expect(latestVersioningProps.className).toBe("h-[calc(100vh-120px)]");
  });

  test("New Automation returns to flows tab and bumps the trigger counter", () => {
    render(<AutomationsPage />);
    expect(latestWorkflowProps.triggerNew).toBe(0);

    fireEvent.click(screen.getByRole("button", { name: /Templates/ }));
    expect(screen.queryByTestId("workflow-automation")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /New Automation/ }));
    expect(screen.getByTestId("workflow-automation")).toBeInTheDocument();
    expect(latestWorkflowProps.triggerNew).toBe(1);
  });

  test("using a template stores it and switches back to the flows tab", () => {
    render(<AutomationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /Templates/ }));

    const template = { id: "tpl-1", name: "Lead Router" };
    act(() => {
      latestGalleryProps.onUseTemplate(template);
    });

    expect(setItemSpy).toHaveBeenCalledWith(
      "selectedTemplate",
      JSON.stringify(template)
    );
    expect(screen.getByTestId("workflow-automation")).toBeInTheDocument();
    expect(screen.queryByTestId("template-gallery")).not.toBeInTheDocument();
  });

  test("agent generator logs generated workflows", () => {
    render(<AutomationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /AI Agents/ }));

    act(() => {
      latestGeneratorProps.onWorkflowGenerated({ id: "wf-1" });
    });
    expect(consoleLogSpy).toHaveBeenCalledWith("Generated:", { id: "wf-1" });
  });

  test("deploying a generated workflow logs it and returns to the flows tab", () => {
    render(<AutomationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /AI Agents/ }));

    act(() => {
      latestGeneratorProps.onDeployWorkflow({ id: "wf-2" });
    });
    expect(consoleLogSpy).toHaveBeenCalledWith("Deploying:", { id: "wf-2" });
    expect(screen.getByTestId("workflow-automation")).toBeInTheDocument();
    expect(latestGeneratorProps.className).toBe("h-[calc(100vh-120px)]");
  });
});
