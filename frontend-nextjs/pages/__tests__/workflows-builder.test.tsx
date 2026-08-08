import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import WorkflowBuilder from "@/pages/workflows/builder";
import { useRouter } from "next/router";
import { useToast } from "@/components/ui/use-toast";

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/workflows/builder",
    pathname: "/workflows/builder",
    query: {},
    asPath: "/workflows/builder",
    isReady: true,
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockToast = jest.fn();

const TEMPLATES = [
  { template_id: "tpl-1", name: "Welcome Flow", description: "Onboarding pipeline" },
  { template_id: "tpl-2", name: "Sales Intel", description: "Competitor monitoring" },
];

const TEMPLATE_2 = {
  template_id: "tpl-2",
  name: "Sales Intel",
  description: "Competitor monitoring",
  steps: [
    {
      step_id: "step-a",
      name: "Competitive Intel",
      description: "Monitor competitor pricing",
      step_type: "agent_execution",
      parameters: [{ name: "agent_id", type: "string", default_value: "competitive_intel" }],
      depends_on: [],
    },
    {
      step_id: "step-b",
      name: "Inventory Check",
      description: "Shopify vs WMS comparison",
      step_type: "agent_execution",
      parameters: [{ name: "agent_id", type: "string", default_value: "inventory_omni" }],
      depends_on: ["step-a"],
    },
  ],
};

const okResponse = (body: any) => ({ ok: true, status: 200, json: async () => body });
const errResponse = (status: number, body: any) => ({ ok: false, status, json: async () => body });

describe("WorkflowBuilder", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Storage.prototype, "getItem").mockReturnValue("test-token");
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    (useRouter as jest.Mock).mockReturnValue({
      route: "/workflows/builder",
      pathname: "/workflows/builder",
      query: {},
      asPath: "/workflows/builder",
      isReady: true,
      push: jest.fn(() => Promise.resolve(true)),
      replace: jest.fn(() => Promise.resolve(true)),
      back: jest.fn(),
    });
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/workflow-templates") return Promise.resolve(okResponse(TEMPLATES));
      if (url === "/api/workflow-templates/tpl-2") return Promise.resolve(okResponse(TEMPLATE_2));
      if (url.includes("/execute")) return Promise.resolve(okResponse({ workflow_status: "completed" }));
      if (url.startsWith("/api/workflow-templates/")) return Promise.resolve(okResponse({ template_id: "tpl-new" }));
      return Promise.resolve(okResponse({}));
    });
  });

  it("loads the workflow template list with the auth header", async () => {
    render(<WorkflowBuilder />);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Welcome Flow" })).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/workflow-templates",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      })
    );
    expect(screen.getByRole("option", { name: "Sales Intel" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Workflow Name")).toHaveValue("My Agent Pipeline");
  });

  it("adds an agent node from the sidebar and saves it as a step", async () => {
    render(<WorkflowBuilder />);
    await waitFor(() => expect(screen.getByText("Workflow Builder")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Competitive Intel"));

    // Agent node appears on the canvas
    expect(screen.getAllByText("Competitive Intel").length).toBeGreaterThanOrEqual(2);

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/workflow-templates",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
          body: expect.stringContaining('"name":"Competitive Intel"'),
        })
      );
    });
    const saveCall = mockFetch.mock.calls.find(
      ([url, opts]) => url === "/api/workflow-templates" && opts?.method === "POST"
    );
    const body = JSON.parse(saveCall[1].body);
    expect(body.steps).toHaveLength(1);
    expect(body.steps[0].step_type).toBe("agent_execution");
    expect(body.steps[0].parameters).toEqual([
      { name: "agent_id", type: "string", default_value: "competitive_intel" },
    ]);
    expect(body.name).toBe("My Agent Pipeline");
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "Saved!" }));
  });

  it("shows an error toast when saving fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/workflow-templates" && (mockFetch as any)._saveFail) {
        return Promise.resolve(errResponse(500, {}));
      }
      if (url === "/api/workflow-templates") return Promise.resolve(okResponse(TEMPLATES));
      return Promise.resolve(okResponse({}));
    });

    render(<WorkflowBuilder />);
    await waitFor(() => expect(screen.getByText("Workflow Builder")).toBeInTheDocument());

    (mockFetch as any)._saveFail = true;
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Failed to save template.", variant: "error" })
      );
    });
  });

  it("asks the user to save before running an unsaved workflow", async () => {
    render(<WorkflowBuilder />);
    await waitFor(() => expect(screen.getByText("Workflow Builder")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Save First", description: "Please save the workflow before running.", variant: "error" })
      );
    });
    expect(mockFetch).not.toHaveBeenCalledWith(expect.stringContaining("/execute"), expect.anything());
  });

  it("runs a saved workflow and reports the status", async () => {
    render(<WorkflowBuilder />);
    await waitFor(() => expect(screen.getByText("Workflow Builder")).toBeInTheDocument());

    // Save first so currentTemplateId is set
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "Saved!" }));
    });

    fireEvent.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/workflow-templates/tpl-new/execute",
        expect.objectContaining({ method: "POST" })
      );
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Completed!", description: "Status: completed" })
    );
  });

  it("shows an execution-failed toast when running fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/execute")) return Promise.resolve(errResponse(500, {}));
      if (url === "/api/workflow-templates") return Promise.resolve(okResponse(TEMPLATES));
      return Promise.resolve(okResponse({ template_id: "tpl-new" }));
    });

    render(<WorkflowBuilder />);
    await waitFor(() => expect(screen.getByText("Workflow Builder")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "Saved!" })));

    fireEvent.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Execution Failed", variant: "error" })
      );
    });
  });

  it("loads a template from the dropdown and converts steps to nodes and edges", async () => {
    render(<WorkflowBuilder />);
    await waitFor(() => expect(screen.getByRole("option", { name: "Sales Intel" })).toBeInTheDocument());

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "tpl-2" } });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Loaded", description: 'Template "Sales Intel" loaded.' })
      );
    });
    // Both agent nodes now on canvas
    expect(screen.getAllByText("Competitive Intel").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Inventory Check")).toBeInTheDocument();
    // Workflow name updated
    expect(screen.getByPlaceholderText("Workflow Name")).toHaveValue("Sales Intel");

    // Save now includes both steps with depends_on wiring
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => {
      const saveCall = mockFetch.mock.calls.find(
        ([url, opts]) => url === "/api/workflow-templates" && opts?.method === "POST"
      );
      expect(saveCall).toBeTruthy();
      const body = JSON.parse(saveCall[1].body);
      expect(body.steps).toHaveLength(2);
      const inventory = body.steps.find((s: any) => s.name === "Inventory Check");
      expect(inventory.depends_on).toEqual(["step-a"]);
    });
  });

  it("shows an error toast when loading a template fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/workflow-templates/tpl-2") return Promise.resolve(errResponse(404, {}));
      if (url === "/api/workflow-templates") return Promise.resolve(okResponse(TEMPLATES));
      return Promise.resolve(okResponse({}));
    });

    render(<WorkflowBuilder />);
    await waitFor(() => expect(screen.getByRole("option", { name: "Sales Intel" })).toBeInTheDocument());

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "tpl-2" } });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Failed to load template.", variant: "error" })
      );
    });
  });

  it("auto-loads a template from the URL query param", async () => {
    (useRouter as jest.Mock).mockReturnValue({
      route: "/workflows/builder",
      pathname: "/workflows/builder",
      query: { template_id: "tpl-2" },
      asPath: "/workflows/builder?template_id=tpl-2",
      isReady: true,
      push: jest.fn(),
      replace: jest.fn(),
      back: jest.fn(),
    });

    render(<WorkflowBuilder />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Workflow Name")).toHaveValue("Sales Intel");
    });
    expect(mockFetch).toHaveBeenCalledWith("/api/workflow-templates/tpl-2", expect.anything());
  });
});
