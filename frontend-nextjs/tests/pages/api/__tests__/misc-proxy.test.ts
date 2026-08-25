const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import searchHandler from "@/pages/api/search/[...path]";
import workflowsOptimizeHandler from "@/pages/api/workflows/optimize";
import zendeskTicketsHandler from "@/pages/api/zendesk/tickets";
import budgetSummaryHandler from "@/pages/api/financial/budgets/summary";
import slackFilesHandler from "@/pages/api/integrations/slack/files";

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_URL;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_URL;
});

describe("pages/api/search/[...path]", () => {
  const invoke = async (
    query: any = {},
    method = "GET",
    body?: any,
    headers: any = {},
  ) => {
    const { req, res } = createMocks({ method, query, body, headers }) as any;
    await searchHandler(req, res);
    return res;
  };

  it("proxies a multi-segment path to the search backend", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, { hits: [{ id: "h1" }] }));
    const res = await invoke({ path: ["emails", "query"] });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ hits: [{ id: "h1" }] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/search/emails/query",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        body: undefined,
      },
    );
  });

  it("uses the path directly when it is a single string", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke({ path: "documents" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/search/documents",
    );
  });

  it("proxies to the bare search root when no path is provided", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke({});
    expect(mockFetch.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/search/");
  });

  it("forwards the Authorization header when present", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke({ path: ["secure"] }, "GET", undefined, {
      authorization: "Bearer token-123",
    });
    expect(mockFetch.mock.calls[0][1].headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer token-123",
    });
  });

  it("forwards the body for POST requests", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, { queued: true }));
    await invoke({ path: ["reindex"] }, "POST", { scope: "all" });
    expect(mockFetch.mock.calls[0][1]).toEqual({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: "all" }),
    });
  });

  it("honours NEXT_PUBLIC_API_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://backend:8100";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke({ path: ["x"] });
    expect(mockFetch.mock.calls[0][0]).toBe("http://backend:8100/api/search/x");
  });

  it("surfaces backend failures with the status text", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => ({}),
      text: async () => "upstream down",
    });
    const res = await invoke({ path: ["x"] });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Backend API error: Bad Gateway",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const res = await invoke({ path: ["x"] });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Failed to connect to search backend",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/workflows/optimize", () => {
  const invoke = async (body?: any, method = "POST") => {
    const { req, res } = createMocks({ method, body }) as any;
    await workflowsOptimizeHandler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("proxies the optimization request to the default IPv4 backend", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, { plan: ["step-1"] }));
    const res = await invoke({ workflow: "wf-1", goal: "cost" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ plan: ["step-1"] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analytics/optimize",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow: "wf-1", goal: "cost" }),
      },
    );
  });

  it("rewrites localhost to 127.0.0.1 in NEXT_PUBLIC_API_URL", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:9000";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke({ workflow: "wf-1" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:9000/api/v1/analytics/optimize",
    );
  });

  it("surfaces backend failures with the status text", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: async () => ({}),
      text: async () => "invalid workflow",
    });
    const res = await invoke({ workflow: "wf-1" });
    expect(res._getStatusCode()).toBe(422);
    expect(res._getJSONData()).toEqual({
      error: "Backend error: Unprocessable Entity",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("timeout"));
    const res = await invoke({ workflow: "wf-1" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal Server Error" });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/zendesk/tickets", () => {
  const invoke = async (method = "GET", query: any = {}, body?: any) => {
    const { req, res } = createMocks({ method, query, body }) as any;
    await zendeskTicketsHandler(req, res);
    return res;
  };

  it("proxies a plain GET list request to the backend", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(true, 200, { tickets: [{ id: 1 }] }),
    );
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ tickets: [{ id: 1 }] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/zendesk/tickets",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        body: undefined,
      },
    );
  });

  it("appends the id path segment and query params", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, { id: 1 }));
    await invoke("GET", { id: "42", status: "open" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/zendesk/tickets/42?status=open",
    );
  });

  it("ignores array ids and forwards remaining query params", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET", { id: ["1", "2"], sort: "updated" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/zendesk/tickets?sort=updated",
    );
  });

  it("sends the request body for non-GET methods", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 201, { id: 99 }));
    const res = await invoke("POST", {}, { subject: "New ticket" });
    expect(res._getStatusCode()).toBe(201);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/zendesk/tickets",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject: "New ticket" }),
      },
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5058";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET");
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://python:5058/api/zendesk/tickets",
    );
  });

  it("mirrors the backend error status and payload", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(false, 404, { error: "Ticket not found" }),
    );
    const res = await invoke("GET", { id: "missing" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "Ticket not found" });
  });

  it("returns 500 with a friendly message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("backend exploded"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Zendesk tickets",
      message: "backend exploded",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("reports Unknown error for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke("GET");
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Zendesk tickets",
      message: "Unknown error",
    });
  });
});

describe("pages/api/financial/budgets/summary", () => {
  const invoke = async (query: any = { userId: "user-1" }, method = "GET") => {
    const { req, res } = createMocks({ method, query }) as any;
    await budgetSummaryHandler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke({ userId: "user-1" }, "POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("returns 400 when userId is missing", async () => {
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "User ID required" });
  });

  it("returns the budget summary for the period", async () => {
    const res = await invoke({ userId: "user-1", period: "current", month: "2026-08" });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.data.totalBudget).toBe(2500);
    expect(body.data.spent).toBe(1837.5);
    expect(body.data.remaining).toBe(662.5);
    expect(body.data.categories).toHaveLength(7);
    expect(body.data.categories[0]).toEqual({
      category: "Dining",
      budgeted: 500,
      spent: 485.75,
      remaining: 14.25,
      utilization: 97.15,
    });
  });

  it("defaults the period to current", async () => {
    const res = await invoke({ userId: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().data.categories).toHaveLength(7);
  });

  it("returns 500 when serializing the summary throws", async () => {
    const { req, res } = createMocks({
      method: "GET",
      query: { userId: "user-1" },
    }) as any;
    const originalStatus = res.status.bind(res);
    let statusCalls = 0;
    res.status = (code: number) => {
      statusCalls += 1;
      if (statusCalls === 1) {
        return {
          json: () => {
            throw new Error("serialize failed");
          },
        };
      }
      return originalStatus(code);
    };
    await budgetSummaryHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to retrieve budget summary",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/slack/files", () => {
  const invoke = async (method = "GET", query: any = {}, body?: any) => {
    const { req, res } = createMocks({ method, query, body }) as any;
    await slackFilesHandler(req, res);
    return res;
  };

  it("proxies a plain GET list request with the current user header", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(true, 200, { files: [{ id: "F1" }] }),
    );
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ files: [{ id: "F1" }] });
    expect(mockFetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/slack/files", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "x-user-id": "current",
      },
      body: undefined,
    });
  });

  it("appends the id path segment and query params", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, { id: "F1" }));
    await invoke("GET", { id: "F1", channel: "C1" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/slack/files/F1?channel=C1",
    );
  });

  it("ignores array ids and forwards remaining query params", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET", { id: ["F1", "F2"], limit: "10" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/slack/files?limit=10",
    );
  });

  it("sends the request body for non-GET methods", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 201, { id: "F2" }));
    const res = await invoke("POST", {}, { name: "upload.txt" });
    expect(res._getStatusCode()).toBe(201);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/files",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-user-id": "current",
        },
        body: JSON.stringify({ name: "upload.txt" }),
      },
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5058";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET");
    expect(mockFetch.mock.calls[0][0]).toBe("http://python:5058/api/slack/files");
  });

  it("mirrors the backend error status and payload", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(false, 404, { error: "File not found" }),
    );
    const res = await invoke("GET", { id: "missing" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "File not found" });
  });

  it("returns 500 with a friendly message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("slack down"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Slack files",
      message: "slack down",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("reports Unknown error for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke("GET");
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Slack files",
      message: "Unknown error",
    });
  });
});
