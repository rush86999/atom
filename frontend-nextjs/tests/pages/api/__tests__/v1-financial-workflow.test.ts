const mockFetch = jest.fn();
const mockExistsSync = jest.fn();
const mockMkdirSync = jest.fn();
const mockReadFileSync = jest.fn();
const mockWriteFileSync = jest.fn();
jest.mock("fs", () => ({
  __esModule: true,
  default: {
    existsSync: mockExistsSync,
    mkdirSync: mockMkdirSync,
    readFileSync: mockReadFileSync,
    writeFileSync: mockWriteFileSync,
  },
  existsSync: mockExistsSync,
  mkdirSync: mockMkdirSync,
  readFileSync: mockReadFileSync,
  writeFileSync: mockWriteFileSync,
}));
jest.spyOn(process, "cwd").mockReturnValue("/tmp/atom-test-cwd");

import { createMocks } from "node-mocks-http";
import accountingHandler from "@/pages/api/accounting/transactions";
import budgetHandler from "@/pages/api/financial/budgets/summary";
import projectsHandler from "@/pages/api/v1/projects";
import projectIdHandler from "@/pages/api/v1/projects/[id]";
import tasksHandler from "@/pages/api/v1/tasks";
import optimizeHandler from "@/pages/api/workflows/optimize";
import testStepHandler from "@/pages/api/workflows/test-step";
import zendeskHandler from "@/pages/api/zendesk/tickets";

const httpResponse = (ok: boolean, status: number, data: any, statusText = ""): any => ({
  ok,
  status,
  statusText,
  json: async () => data,
  text: async () => (typeof data === "string" ? data : JSON.stringify(data)),
});

describe("pages/api/accounting/transactions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("returns the review queue for GET", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { queue: [] }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await accountingHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ queue: [] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/ai-accounting/review-queue",
      {
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("forwards the authorization header when present", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({
      method: "GET",
      headers: { authorization: "Bearer tok" },
    }) as any;
    await accountingHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/ai-accounting/review-queue",
      {
        headers: { Authorization: "Bearer tok", "Content-Type": "application/json" },
      },
    );
  });

  it("returns backend text as the error body for GET failures", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 502, "bad gateway"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await accountingHandler(req, res);
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({ error: "bad gateway" });
  });

  it("ingests a transaction via POST", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { ok: true }));
    const body = { amount: 10 };
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await accountingHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/ai-accounting/transactions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  });

  it("returns backend text as the error body for POST failures", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 400, "invalid"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await accountingHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "invalid" });
  });

  it("returns 500 when GET fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await accountingHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to fetch transactions" });
  });

  it("returns 500 when POST fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await accountingHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to ingest transaction" });
  });

  it("rejects other methods with 405", async () => {
    const { req, res } = createMocks({ method: "DELETE" }) as any;
    await accountingHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });
});

describe("pages/api/financial/budgets/summary", () => {
  beforeEach(() => {
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-GET with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await budgetHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
  });

  it("returns 400 when userId is missing", async () => {
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await budgetHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "User ID required" });
  });

  it("returns the mock budget summary for a userId", async () => {
    const { req, res } = createMocks({ method: "GET", query: { userId: "u1", period: "monthly", month: "2026-08", categories: "a,b" } }) as any;
    await budgetHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.data.totalBudget).toBe(2500);
    expect(body.data.spent).toBe(1837.5);
    expect(body.data.remaining).toBe(662.5);
    expect(body.data.categories).toHaveLength(7);
    expect(body.data.categories[3]).toEqual({
      category: "Entertainment",
      budgeted: 200,
      spent: 235.3,
      remaining: -35.3,
      utilization: 117.65,
    });
  });
});

describe("pages/api/v1/projects", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockExistsSync.mockReturnValue(false);
    mockMkdirSync.mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("lists projects from the data file", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue(JSON.stringify([{ id: "p1", name: "Alpha" }]));
    const { req, res } = createMocks({ method: "GET" }) as any;
    projectsHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ projects: [{ id: "p1", name: "Alpha" }] });
  });

  it("returns an empty list when the data file is missing", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    projectsHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ projects: [] });
  });

  it("returns an empty list when the data file is corrupted", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue("{not json");
    const { req, res } = createMocks({ method: "GET" }) as any;
    projectsHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ projects: [] });
  });

  it("creates a project via POST", async () => {
    mockExistsSync.mockReturnValue(false);
    const { req, res } = createMocks({ method: "POST", body: { name: "New" } }) as any;
    projectsHandler(req, res);
    expect(res._getStatusCode()).toBe(201);
    const body = res._getJSONData();
    expect(body.project.name).toBe("New");
    expect(body.project.id).toMatch(/^project_/);
    expect(body.project.tasks).toEqual([]);
    expect(mockWriteFileSync).toHaveBeenCalledWith(
      "/tmp/atom-test-cwd/data/projects.json",
      expect.stringContaining('"name": "New"'),
    );
  });

  it("rejects other methods with 405", async () => {
    const { req, res } = createMocks({ method: "PUT" }) as any;
    projectsHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
  });
});

describe("pages/api/v1/projects/[id]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockExistsSync.mockReturnValue(false);
    mockMkdirSync.mockImplementation(() => undefined);
  });

  it("updates an existing project via PUT", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue(JSON.stringify([{ id: "project_x", name: "Old" }]));
    const { req, res } = createMocks({
      method: "PUT",
      query: { id: "project_x" },
      body: { name: "Updated" },
    }) as any;
    projectIdHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.project.name).toBe("Updated");
    expect(body.project.id).toBe("project_x");
    expect(mockWriteFileSync).toHaveBeenCalled();
  });

  it("returns 404 when the project does not exist", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue(JSON.stringify([{ id: "other" }]));
    const { req, res } = createMocks({
      method: "PUT",
      query: { id: "nope" },
      body: { name: "X" },
    }) as any;
    projectIdHandler(req, res);
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "Project not found" });
    expect(mockWriteFileSync).not.toHaveBeenCalled();
  });

  it("rejects non-PUT with 405", async () => {
    const { req, res } = createMocks({ method: "GET", query: { id: "x" } }) as any;
    projectIdHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
  });
});

describe("pages/api/v1/tasks", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockExistsSync.mockReturnValue(false);
    mockMkdirSync.mockImplementation(() => undefined);
  });

  it("lists tasks", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    tasksHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ tasks: [] });
  });

  it("creates a task via POST with timestamps and default dueDate", async () => {
    const { req, res } = createMocks({ method: "POST", body: { title: "T" } }) as any;
    tasksHandler(req, res);
    expect(res._getStatusCode()).toBe(201);
    const task = res._getJSONData().task;
    expect(task.title).toBe("T");
    expect(task.id).toMatch(/^task_/);
    expect(task.createdAt).toBe(task.updatedAt);
    expect(task.dueDate).toBe(task.createdAt);
    expect(mockWriteFileSync).toHaveBeenCalledWith("/tmp/atom-test-cwd/data/tasks.json", expect.any(String));
  });

  it("preserves a user-provided dueDate", async () => {
    const { req, res } = createMocks({ method: "POST", body: { title: "T", dueDate: "2026-09-01" } }) as any;
    tasksHandler(req, res);
    expect(res._getJSONData().task.dueDate).toBe("2026-09-01");
  });

  it("rejects other methods with 405", async () => {
    const { req, res } = createMocks({ method: "DELETE" }) as any;
    tasksHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
  });
});

describe("pages/api/workflows/optimize", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await optimizeHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("forwards the payload to the analytics optimize endpoint", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { optimization: [] }));
    const body = { workflow: "w1" };
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await optimizeHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ optimization: [] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analytics/optimize",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    );
  });

  it("replaces localhost with 127.0.0.1 in the api url", async () => {
    const old = process.env.NEXT_PUBLIC_API_URL;
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:9999";
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await optimizeHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe("http://127.0.0.1:9999/api/v1/analytics/optimize");
    if (old === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = old;
  });

  it("mirrors backend error status with statusText", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 503, "no", "Service Unavailable"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await optimizeHandler(req, res);
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({ error: "Backend error: Service Unavailable" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await optimizeHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal Server Error" });
  });
});

describe("pages/api/workflows/test-step", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    jest.spyOn(console, "log").mockImplementation(() => {});
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "PUT" }) as any;
    await testStepHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
  });

  it("forwards the payload to the test-step endpoint", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { success: true }));
    const body = { stepId: "s1" };
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await testStepHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/workflows/test-step",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    );
  });

  it("returns backend error text on failure", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 422, "invalid step"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await testStepHandler(req, res);
    expect(res._getStatusCode()).toBe(422);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Backend error: 422 - invalid step",
    });
  });

  it("returns 500 with error message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("boom"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await testStepHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ success: false, error: "boom" });
  });

  it("falls back to a generic message when the rejection has no message", async () => {
    mockFetch.mockRejectedValue({});
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await testStepHandler(req, res);
    expect(res._getJSONData()).toEqual({ success: false, error: "Failed to test workflow step" });
  });
});

describe("pages/api/zendesk/tickets", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("lists tickets with query params forwarded", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { tickets: [] }));
    const { req, res } = createMocks({ method: "GET", query: { status: "open" } }) as any;
    await zendeskHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ tickets: [] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/zendesk/tickets?status=open",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        body: undefined,
      },
    );
  });

  it("appends the ticket id to the URL", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { ticket: {} }));
    const { req, res } = createMocks({ method: "GET", query: { id: "42" } }) as any;
    await zendeskHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/zendesk/tickets/42");
  });

  it("sends the body for non-GET methods", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 201, { ok: true }));
    const body = { subject: "S" };
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await zendeskHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/zendesk/tickets",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  });

  it("mirrors backend status", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 404, { detail: "missing" }));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await zendeskHandler(req, res);
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ detail: "missing" });
  });

  it("returns 500 with message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await zendeskHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Zendesk tickets",
      message: "down",
    });
  });

  it("falls back to Unknown error for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("x");
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await zendeskHandler(req, res);
    expect(res._getJSONData().message).toBe("Unknown error");
  });
});
