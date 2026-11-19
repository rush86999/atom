import React from "react";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
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
      <button onClick={() => props.onRun?.()}>
        run-from-builder
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

  describe("run flow with parameter entry", () => {
    function mockTemplateAndReady(overrides: {
      results?: () => Promise<any>;
      status?: () => Promise<any>;
    } = {}) {
      mockFetch.mockImplementation((url: string, opts?: any) => {
        if (url === "/api/workflow-templates/wf-1") {
          return Promise.resolve(okResponse(TEMPLATE_WITH_INPUTS));
        }
        if (url.includes("/readiness")) {
          return Promise.resolve(
            okResponse({ success: true, ready: true, missing: [], connect_urls: [] }),
          );
        }
        if (url === "/api/workflow-templates/wf-1/execute" && opts?.method === "POST") {
          return Promise.resolve(
            okResponse({ status: "success", execution_id: "workflow_exe1" }),
          );
        }
        if (url.includes("/executions/") && url.includes("/status")) {
          if (overrides.status) return overrides.status();
          return Promise.resolve(
            okResponse({
              success: true,
              execution_id: "workflow_exe1",
              workflow_id: "workflow_exe1",
              status: "completed",
              error: null,
            }),
          );
        }
        if (url.includes("/results")) {
          if (overrides.results) return overrides.results();
          return Promise.resolve(
            okResponse({
              success: true,
              status: "completed",
              error: null,
              steps: [
                { step_id: "scan_inbox", step_type: "action", status: "completed" },
                { step_id: "approval_gate", step_type: "approval", status: "awaiting_approval", notes: "waiting for human OK" },
              ],
              outputs: { chased_count: 3 },
            }),
          );
        }
        return Promise.resolve(okResponse({}));
      });
    }

    it("opens the parameter dialog from the Run action", async () => {
      mockTemplateAndReady();
      render(<WorkflowEditorPage />);
      await screen.findByTestId("workflow-builder");

      fireEvent.click(screen.getByRole("button", { name: /run-from-builder/i }));

      const dialog = await screen.findByRole("dialog");
      expect(within(dialog).getByText(/Run "Competitor Watch"/)).toBeInTheDocument();
      expect(within(dialog).getByText("Overdue after (days)")).toBeInTheDocument();
      // Optional input renders too
      expect(within(dialog).getByText("Client email domain")).toBeInTheDocument();
    });

    it("blocks submit and lists missing required inputs", async () => {
      mockTemplateAndReady();
      render(<WorkflowEditorPage />);
      await screen.findByTestId("workflow-builder");

      fireEvent.click(screen.getByRole("button", { name: /run-from-builder/i }));
      const dialog = await screen.findByRole("dialog");
      fireEvent.click(within(dialog).getByRole("button", { name: /Run workflow/i }));

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({ title: "Missing required inputs" }),
        );
      });
      expect(
        mockFetch.mock.calls.filter(([u]: [string]) => u.includes("/execute")),
      ).toHaveLength(0);
    });

    it("POSTs entered parameters flat to /execute and toasts the execution id", async () => {
      mockTemplateAndReady();
      render(<WorkflowEditorPage />);
      await screen.findByTestId("workflow-builder");

      fireEvent.click(screen.getByRole("button", { name: /run-from-builder/i }));
      const dialog = await screen.findByRole("dialog");

      fireEvent.change(within(dialog).getByLabelText(/Overdue after/), {
        target: { value: "21" },
      });
      fireEvent.change(within(dialog).getByLabelText(/Client email domain/), {
        target: { value: "acmecorp.com" },
      });
      fireEvent.click(within(dialog).getByRole("button", { name: /Run workflow/i }));

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "Workflow started",
            description: expect.stringContaining("workflow_exe1"),
          }),
        );
      });
      const [, callOpts] = mockFetch.mock.calls.find(
        ([u]: [string]) => u === "/api/workflow-templates/wf-1/execute",
      )!;
      expect(callOpts.method).toBe("POST");
      expect(JSON.parse(callOpts.body)).toEqual({
        client_email_domain: "acmecorp.com",
        overdue_days: "21",
      });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      // Status chip polls and reflects terminal state.
      const chip = await screen.findByTestId("execution-status-chip");
      await waitFor(() => {
        expect(chip).toHaveTextContent(/completed/);
      });

      // Clicking the chip opens the step-results panel.
      fireEvent.click(within(chip).getByRole("button"));
      const panel = await screen.findByTestId("execution-results-panel");
      await waitFor(() => {
        expect(panel).toHaveTextContent("scan_inbox");
      });
      expect(panel).toHaveTextContent("awaiting_approval");
      expect(panel).toHaveTextContent("waiting for human OK");
    });

    it("shows a safe retry when results fail to load, then retries the same GET", async () => {
      let resultsAttempt = 0;
      mockTemplateAndReady({
        results: () => {
          resultsAttempt += 1;
          if (resultsAttempt === 1) {
            return Promise.resolve(
              errResponse(409, { detail: "results not ready: internal trace 123" }),
            );
          }
          return Promise.resolve(
            okResponse({
              success: true,
              status: "completed",
              error: null,
              steps: [{ step_id: "scan_inbox", step_type: "action", status: "completed" }],
              outputs: { chased_count: 3 },
            }),
          );
        },
      });

      render(<WorkflowEditorPage />);
      await screen.findByTestId("workflow-builder");

      fireEvent.click(screen.getByRole("button", { name: /run-from-builder/i }));
      const dialog = await screen.findByRole("dialog");
      fireEvent.change(within(dialog).getByLabelText(/Overdue after/), {
        target: { value: "21" },
      });
      fireEvent.click(within(dialog).getByRole("button", { name: /Run workflow/i }));

      const chip = await screen.findByTestId("execution-status-chip");
      fireEvent.click(within(chip).getByRole("button"));

      const panel = await screen.findByTestId("execution-results-panel");
      await waitFor(() => {
        expect(panel).toHaveTextContent("Could not load run results.");
      });
      expect(panel).not.toHaveTextContent("internal trace 123");

      fireEvent.click(within(panel).getByRole("button", { name: /retry/i }));

      await waitFor(() => {
        expect(panel).toHaveTextContent("scan_inbox");
      });
      expect(panel).not.toHaveTextContent("Could not load run results.");

      const resultCalls = mockFetch.mock.calls.filter(
        ([url]: [string]) => url === "/api/workflow-templates/executions/workflow_exe1/results",
      );
      expect(resultCalls).toHaveLength(2);
      const executeCalls = mockFetch.mock.calls.filter(
        ([url]: [string]) => url === "/api/workflow-templates/wf-1/execute",
      );
      expect(executeCalls).toHaveLength(1);
    });

    it("refreshes an open results panel with final output when a running run completes", async () => {
      jest.useFakeTimers();
      try {
        let statusAttempt = 0;
        let resultsAttempt = 0;
        mockTemplateAndReady({
          status: () => {
            statusAttempt += 1;
            return Promise.resolve(
              okResponse({
                success: true,
                execution_id: "workflow_exe1",
                workflow_id: "workflow_exe1",
                status: statusAttempt === 1 ? "running" : "completed",
                error: null,
              }),
            );
          },
          results: () => {
            resultsAttempt += 1;
            if (resultsAttempt === 1) {
              // The first GET races the run and succeeds with no history yet.
              return Promise.resolve(
                okResponse({
                  success: true,
                  status: "running",
                  error: null,
                  steps: [],
                  outputs: null,
                }),
              );
            }
            return Promise.resolve(
              okResponse({
                success: true,
                status: "completed",
                error: null,
                steps: [
                  { step_id: "scan_inbox", step_type: "action", status: "completed" },
                  { step_id: "send_digest", step_type: "action", status: "completed" },
                ],
                outputs: { chased_count: 3 },
              }),
            );
          },
        });

        render(<WorkflowEditorPage />);
        await screen.findByTestId("workflow-builder");

        fireEvent.click(screen.getByRole("button", { name: /run-from-builder/i }));
        const dialog = await screen.findByRole("dialog");
        fireEvent.change(within(dialog).getByLabelText(/Overdue after/), {
          target: { value: "21" },
        });
        fireEvent.click(within(dialog).getByRole("button", { name: /Run workflow/i }));

        // Open the panel while the status is still running, so the first
        // results GET returns an empty (but successful) payload.
        const chip = await screen.findByTestId("execution-status-chip");
        fireEvent.click(within(chip).getByRole("button"));
        const panel = await screen.findByTestId("execution-results-panel");

        await waitFor(() => {
          expect(chip).toHaveTextContent(/running/i);
          expect(panel).toHaveTextContent("No step history recorded.");
        });

        // Advance the real status poll to its terminal response.
        await act(async () => {
          jest.advanceTimersByTime(3000);
        });

        await waitFor(() => {
          expect(chip).toHaveTextContent(/completed/i);
          expect(panel).toHaveTextContent("scan_inbox");
          expect(panel).toHaveTextContent("send_digest");
          expect(panel).toHaveTextContent("chased_count");
        });
        expect(panel).not.toHaveTextContent("No step history recorded.");

        const resultCalls = mockFetch.mock.calls.filter(
          ([url]: [string]) => url === "/api/workflow-templates/executions/workflow_exe1/results",
        );
        expect(resultCalls).toHaveLength(2);
        const executeCalls = mockFetch.mock.calls.filter(
          ([url]: [string]) => url === "/api/workflow-templates/wf-1/execute",
        );
        expect(executeCalls).toHaveLength(1);
      } finally {
        jest.useRealTimers();
      }
    });
  });
});
});
