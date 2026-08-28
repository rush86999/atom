const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/lib/auth", () => ({ authOptions: { providers: [] } }));

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/agent/nlu";

const mockFetch = jest.fn();

const mockSession = {
  user: { id: "user-1", email: "user@example.com" },
};

function backendJson(body: any, ok = true): Response {
  return {
    ok,
    json: async () => body,
  } as unknown as Response;
}

describe("pages/api/agent/nlu", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    (global as any).fetch = mockFetch;
  });

  const invoke = async (method = "POST", body: any = {}, session: any = mockSession) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405 and Allow header", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getData()).toContain("Method GET Not Allowed");
    expect(res.getHeader("Allow")).toEqual(["POST"]);
  });

  it("returns 400 when message is missing", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe(
      "Message is required and must be a string",
    );
    expect(res._getJSONData().user).toBe("user@example.com");
  });

  it("returns 400 with a non-string message without crashing when session is null", async () => {
    const res = await invoke("POST", { message: 123 }, null);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe(
      "Message is required and must be a string",
    );
  });

  it("maps a backend WORKFLOW intent into frontend format", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        intent: "CREATE_WORKFLOW",
        entities: {
          service: "slack",
          action: "send",
          time_expression: "tomorrow",
          workflow_ref: "Q3 report",
        },
        ai_provider_used: "deepseek",
      }),
    );
    const res = await invoke("POST", { message: "send q3 report to slack tomorrow" });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.primaryGoal).toBe("workflow");
    expect(body.primaryGoalConfidence).toBe(0.85);
    expect(body.llmPowered).toBe(true);
    expect(body.provider).toBe("deepseek");
    expect(body.extractedParameters).toEqual({
      service: "slack",
      action: "send",
      time: "tomorrow",
      subject: "Q3 report",
    });
    expect(body.rawSubAgentResponses.workflow.isWorkflowRequest).toBe(true);
    expect(body.rawSubAgentResponses.workflow.trigger).toEqual({
      service: "slack",
      event: "user_request",
    });
    expect(body.userContext.userId).toBe("user-1");
    expect(body.userContext.email).toBe("user@example.com");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/ai/nlu"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("prefers a structured workflow_suggestion from the backend", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        intent: "GENERAL",
        workflow_suggestion: {
          nodes: [
            { service: "gmail", action: "search", params: { query: "invoices" } },
            { service: "slack", action: "send", params: { channel: "general" } },
          ],
        },
      }),
    );
    const res = await invoke("POST", { message: "find invoices and post them" });
    const workflow = res._getJSONData().rawSubAgentResponses.workflow;
    expect(workflow.isWorkflowRequest).toBe(true);
    expect(workflow.trigger).toEqual({ service: "manual", event: "start" });
    expect(workflow.actions).toEqual([
      { service: "gmail", action: "search", parameters: { query: "invoices" } },
      { service: "slack", action: "send", parameters: { channel: "general" } },
    ]);
  });

  it("falls back to tasks_generated when full structure is absent", async () => {
    mockFetch.mockResolvedValue(
      backendJson({ intent: "CREATE_WORKFLOW", tasks_generated: ["fetch", "notify"] }),
    );
    const res = await invoke("POST", { message: "do the thing" });
    const workflow = res._getJSONData().rawSubAgentResponses.workflow;
    expect(workflow.isWorkflowRequest).toBe(true);
    expect(workflow.actions).toEqual([
      { service: "general", action: "fetch", parameters: {} },
      { service: "general", action: "notify", parameters: {} },
    ]);
  });

  it("maps unknown intents to general and detects entities from message text", async () => {
    mockFetch.mockResolvedValue(
      backendJson({ intent: "UNKNOWN", entities: {} }),
    );
    const res = await invoke("POST", {
      message: "create a google calendar event tomorrow at 2:00 pm",
    });
    const body = res._getJSONData();
    expect(body.primaryGoal).toBe("general");
    expect(body.extractedParameters.service).toBe("calendar");
    expect(body.extractedParameters.action).toBe("create");
  });

  it("uses keyword fallback when backend responds non-OK", async () => {
    mockFetch.mockResolvedValue(backendJson({ error: "nope" }, false));
    const res = await invoke("POST", { message: "create workflow to send email" });
    const body = res._getJSONData();
    expect(body.llmPowered).toBe(false);
    expect(body.primaryGoal).toBe("workflow");
    expect(body.primaryGoalConfidence).toBe(0.6);
    expect(body.extractedParameters.action).toBe("create");
    expect(body.rawSubAgentResponses.workflow.isWorkflowRequest).toBe(true);
    expect(body.rawSubAgentResponses.workflow.trigger).toEqual({
      service: "email",
      event: "user_request",
    });
  });

  it("uses keyword fallback when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { message: "set up a meeting tomorrow at 3:00 pm" });
    const body = res._getJSONData();
    expect(body.llmPowered).toBe(false);
    expect(body.primaryGoal).toBe("calendar");
    expect(body.extractedParameters.time).toBe("3:00 pm");
  });

  it("treats unknown text as general intent with low confidence", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { message: "blah blah blah" });
    const body = res._getJSONData();
    expect(body.primaryGoal).toBe("general");
    expect(body.primaryGoalConfidence).toBe(0.3);
    expect(body.rawSubAgentResponses.workflow.isWorkflowRequest).toBe(false);
  });
});
