import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import WorkflowEditorPage from "@/pages/workflows/editor/[id]";
import { useRouter } from "next/router";
import { useToast } from "@/components/ui/use-toast";
import WorkflowBuilder from "@/components/Automations/WorkflowBuilder";

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/workflows/editor/wf-1",
    pathname: "/workflows/editor/[id]",
    query: { id: "wf-1" },
    asPath: "/workflows/editor/wf-1",
    isReady: true,
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

jest.mock("@/components/Automations/WorkflowBuilder", () => ({
  __esModule: true,
  default: (props: any) => (
    <div data-testid="workflow-builder">
      <span data-testid="builder-workflow-id">{props.workflowId || "none"}</span>
      <span data-testid="builder-nodes">{props.initialData ? props.initialData.nodes.length : 0}</span>
      <span data-testid="builder-edges">{props.initialData ? props.initialData.edges.length : 0}</span>
      <ul data-testid="builder-node-types">
        {(props.initialData?.nodes || []).map((n: any) => (
          <li key={n.id}>
            {n.id}:{n.type}:{n.data?.label}
          </li>
        ))}
      </ul>
      <button onClick={() => props.onSave({ nodes: props.initialData?.nodes || [], edges: props.initialData?.edges || [] })}>
        save-from-builder
      </button>
    </div>
  ),
}));

const mockToast = jest.fn();

const WORKFLOW = {
  template_id: "wf-1",
  name: "Competitor Watch",
  description: "Watch competitors",
  steps: [
    {
      step_id: "s1",
      name: "Fetch Competitors",
      description: "Gather pricing",
      step_type: "agent_execution",
      parameters: [{ name: "agent_id", type: "string", default_value: "competitive_intel" }],
      depends_on: [],
    },
    {
      step_id: "s2",
      name: "Summarize",
      description: "LLM summary",
      step_type: "llm_process",
      parameters: [],
      depends_on: ["s1"],
    },
    {
      step_id: "s3",
      name: "Conditional Alert",
      description: "Price drop check",
      step_type: "condition",
      parameters: [],
      depends_on: ["s2"],
    },
  ],
};

const okResponse = (body: any) => ({ ok: true, status: 200, json: async () => body });
const errResponse = (status: number, body: any) => ({ ok: false, status, json: async () => body });

describe("WorkflowEditorPage", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Storage.prototype, "getItem").mockReturnValue("test-token");
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    (useRouter as jest.Mock).mockReturnValue({
      route: "/workflows/editor/wf-1",
      pathname: "/workflows/editor/[id]",
      query: { id: "wf-1" },
      asPath: "/workflows/editor/wf-1",
      isReady: true,
      push: jest.fn(() => Promise.resolve(true)),
      replace: jest.fn(() => Promise.resolve(true)),
      back: jest.fn(),
    });
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/workflow-templates/wf-1") return Promise.resolve(okResponse(WORKFLOW));
      return Promise.resolve(okResponse({}));
    });  });

  it("shows the loading spinner while the workflow is fetched", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<WorkflowEditorPage />);
    expect(document.querySelector(".animate-spin")).not.toBeNull();
    expect(screen.queryByTestId("workflow-builder")).not.toBeInTheDocument();
  });

  it("fetches the workflow and converts steps to nodes and edges for the builder", async () => {
    render(<WorkflowEditorPage />);

    await waitFor(() => {
      expect(screen.getByTestId("workflow-builder")).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/workflow-templates/wf-1",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      })
    );

    expect(screen.getByTestId("builder-workflow-id")).toHaveTextContent("wf-1");
    expect(screen.getByTestId("builder-nodes")).toHaveTextContent("3");
    expect(screen.getByTestId("builder-edges")).toHaveTextContent("2");

    // Backend step types mapped to node types
    const nodeTypes = screen.getByTestId("builder-node-types");
    expect(nodeTypes).toHaveTextContent("s1:agent:Fetch Competitors");
    expect(nodeTypes).toHaveTextContent("s2:ai_node:Summarize");
    expect(nodeTypes).toHaveTextContent("s3:condition:Conditional Alert");
  });

  it("creates a default start trigger node when the workflow has no steps", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(
        okResponse({ template_id: "wf-1", name: "Empty Flow", description: "", steps: [] })
      )
    );

    render(<WorkflowEditorPage />);

    await waitFor(() => {
      expect(screen.getByTestId("builder-nodes")).toHaveTextContent("1");
    });
    expect(screen.getByTestId("builder-node-types")).toHaveTextContent("start:trigger:Start Trigger");
    expect(screen.getByTestId("builder-edges")).toHaveTextContent("0");
  });

  it("shows an error toast when the workflow fails to load", async () => {
    mockFetch.mockImplementation((url: string) => Promise.resolve(errResponse(404, {})));

    render(<WorkflowEditorPage />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Failed to load workflow template", variant: "error" })
      );
    });
    // Loading finishes: builder still renders (with no initial data)
    await waitFor(() => {
      expect(screen.getByTestId("workflow-builder")).toBeInTheDocument();
    });
    expect(screen.getByTestId("builder-nodes")).toHaveTextContent("0");
  });

  it("saves via the builder: PUTs mapped steps back to the backend", async () => {
    render(<WorkflowEditorPage />);
    await waitFor(() => expect(screen.getByTestId("workflow-builder")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /save-from-builder/i }));

    await waitFor(() => {
      const saveCall = mockFetch.mock.calls.find(
        ([url, opts]) => url === "/api/workflow-templates/wf-1" && opts?.method === "PUT"
      );
      expect(saveCall).toBeTruthy();
      const body = JSON.parse(saveCall[1].body);
      expect(body.name).toBe("Competitor Watch");
      expect(body.steps).toHaveLength(3);
      // Node types mapped back to backend step types
      expect(body.steps[0].step_type).toBe("agent_execution");
      expect(body.steps[1].step_type).toBe("llm_process");
      expect(body.steps[2].step_type).toBe("condition");
      // depends_on derived from edges
      const s3 = body.steps.find((s: any) => s.step_id === "s3");
      expect(s3.depends_on).toEqual(["s2"]);
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Saved", description: "Workflow template updated successfully." })
    );
  });

  it("shows an error toast when saving fails", async () => {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === "/api/workflow-templates/wf-1" && opts?.method === "PUT") {
        return Promise.resolve(errResponse(500, {}));
      }
      if (url === "/api/workflow-templates/wf-1") return Promise.resolve(okResponse(WORKFLOW));
      return Promise.resolve(okResponse({}));
    });

    render(<WorkflowEditorPage />);
    await waitFor(() => expect(screen.getByTestId("workflow-builder")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /save-from-builder/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Failed to save workflow", variant: "error" })
      );
    });
  });

  describe("first-run checklist", () => {
    const TEMPLATE_WITH_INPUTS = {
      ...WORKFLOW,
      template_id: "wf-1",
      inputs: [
        { name: "client_email_domain", label: "Client email domain", type: "string", required: false },
        { name: "overdue_days", label: "Overdue after (days)", type: "number", required: true },
      ],
    };

    it("shows required inputs and a connect CTA when not ready", async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url === "/api/workflow-templates/wf-1") {
          return Promise.resolve(okResponse(TEMPLATE_WITH_INPUTS));
        }
        if (url.includes("/readiness")) {
          return Promise.resolve(
            okResponse({
              success: true,
              ready: false,
              connected: [],
              missing: ["gmail"],
              connect_urls: ["/integrations?connect=gmail"],
            }),
          );
        }
        return Promise.resolve(okResponse({}));
      });

      render(<WorkflowEditorPage />);
      const banner = await screen.findByTestId("first-run-checklist");
      expect(banner).toHaveTextContent(/Overdue after \(days\)/);
      expect(banner).not.toHaveTextContent("Client email domain");

      const cta = screen.getByRole("link", { name: /Connect gmail/i });
      expect(cta).toHaveAttribute("href", "/integrations?connect=gmail");
    });

    it("hides the checklist when ready and no required inputs", async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url === "/api/workflow-templates/wf-1") {
          // WORKFLOW declares no required inputs.
          return Promise.resolve(okResponse(WORKFLOW));
        }
        if (url.includes("/readiness")) {
          return Promise.resolve(
            okResponse({ success: true, ready: true, missing: [], connect_urls: [] }),
          );
        }
        return Promise.resolve(okResponse({}));
      });

      render(<WorkflowEditorPage />);
      await waitFor(() =>
        expect(screen.getByTestId("workflow-builder")).toBeInTheDocument(),
      );
      expect(screen.queryByTestId("first-run-checklist")).not.toBeInTheDocument();
    });

    it("dismisses the checklist", async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url === "/api/workflow-templates/wf-1") {
          return Promise.resolve(okResponse(TEMPLATE_WITH_INPUTS));
        }
        if (url.includes("/readiness")) {
          return Promise.resolve(
            okResponse({
              success: true,
              ready: false,
              missing: ["gmail"],
              connect_urls: ["/integrations?connect=gmail"],
            }),
          );
        }
        return Promise.resolve(okResponse({}));
      });

      render(<WorkflowEditorPage />);
      await screen.findByTestId("first-run-checklist");
      fireEvent.click(screen.getByRole("button", { name: /Dismiss/i }));
      expect(screen.queryByTestId("first-run-checklist")).not.toBeInTheDocument();
    });
  });
});
