import React from "react";
import { render, screen } from "@testing-library/react";
import WorkflowEditor from "@/components/Automations/WorkflowEditor";
import TriggerSettings from "@/components/Automations/TriggerSettings";

jest.mock("@/components/Automations/ExecutionHistoryList", () => () => null);
jest.mock("@/components/Automations/ExecutionDetailView", () => () => null);
jest.mock("@/components/Automations/WorkflowScheduler", () => () => null);
jest.mock("@/components/Automations/IntegrationSelector", () => () => null);

describe("WorkflowEditor", () => {
  const workflow = {
    id: "wf-1",
    name: "Lead Routing",
    description: "Route inbound leads",
    version: "1.0.0",
    nodes: [],
    connections: [],
    triggers: [],
    enabled: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  it("renders with navigation and workflow name", () => {
    render(<WorkflowEditor workflow={workflow} />);
    expect(
      screen.getByRole("heading", { name: "Workflow Editor" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Lead Routing")).toBeInTheDocument();
    expect(
      screen.getByText(/placeholder for the WorkflowEditor component/i),
    ).toBeInTheDocument();
  });

  it("hides navigation and uses compact padding in compactView", () => {
    const { container } = render(
      <WorkflowEditor workflow={workflow} compactView showNavigation={false} />,
    );
    expect(
      screen.queryByRole("heading", { name: "Workflow Editor" }),
    ).not.toBeInTheDocument();
    expect(container.querySelector(".p-2")).toBeInTheDocument();
    expect(
      screen.getByText(/placeholder for the WorkflowEditor component/i),
    ).toBeInTheDocument();
  });
});

describe("TriggerSettings", () => {
  it("renders its placeholder text", () => {
    render(<TriggerSettings />);
    expect(screen.getByText("Trigger Settings")).toBeInTheDocument();
  });
});
