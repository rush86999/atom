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

const BACKEND_URL = "http://backend.test";
const AUTH_HEADER = "Bearer controlled-financial-token";

const malformedResponse = (status = 200): any => ({
  ok: status >= 200 && status < 300,
  status,
  statusText: "",
  json: async () => {
    throw new SyntaxError("Unexpected token < in JSON");
  },
  text: async () => "<html>not json</html>",
});

const originalFetch = (global as any).fetch;
const originalBackendUrl = process.env.BACKEND_URL;
const originalPythonBackendUrl = process.env.PYTHON_BACKEND_URL;
const originalNextPublicApiUrl = process.env.NEXT_PUBLIC_API_URL;

const installBackendTransport = () => {
  process.env.BACKEND_URL = BACKEND_URL;
  delete process.env.PYTHON_BACKEND_URL;
  delete process.env.NEXT_PUBLIC_API_URL;
  (global as any).fetch = mockFetch;
};

const restoreBackendTransport = () => {
  if (originalFetch === undefined) delete (global as any).fetch;
  else (global as any).fetch = originalFetch;
  if (originalBackendUrl === undefined) delete process.env.BACKEND_URL;
  else process.env.BACKEND_URL = originalBackendUrl;
  if (originalPythonBackendUrl === undefined) delete process.env.PYTHON_BACKEND_URL;
  else process.env.PYTHON_BACKEND_URL = originalPythonBackendUrl;
  if (originalNextPublicApiUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
  else process.env.NEXT_PUBLIC_API_URL = originalNextPublicApiUrl;
};

const expectNoFilesystemAccess = () => {
  expect(mockExistsSync).not.toHaveBeenCalled();
  expect(mockMkdirSync).not.toHaveBeenCalled();
  expect(mockReadFileSync).not.toHaveBeenCalled();
  expect(mockWriteFileSync).not.toHaveBeenCalled();
};

type InvokeOptions = {
  query?: Record<string, any>;
  body?: any;
  headers?: Record<string, string>;
};

const invoke = async (
  handler: (req: any, res: any) => Promise<void> | void,
  method: string,
  { query = {}, body, headers = { authorization: AUTH_HEADER } }: InvokeOptions = {},
) => {
  const { req, res } = createMocks({ method, query, body, headers }) as any;
  req.body = body;
  await handler(req, res);
  return res;
};

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
    installBackendTransport();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    restoreBackendTransport();
  });

  it("lists projects from the authenticated backend without reading local files", async () => {
    const projects = [{ id: "p1", name: "Alpha" }];
    mockFetch.mockResolvedValue(httpResponse(true, 200, { projects }));

    const res = await invoke(projectsHandler, "GET", {
      query: { owner: "u1", id: "ignored" },
    });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ projects });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    // A collection id query is not a dynamic route parameter.
    expect(url).toBe(`${BACKEND_URL}/api/v1/projects?owner=u1&id=ignored`);
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
    expect(init.headers).toEqual({
      Authorization: AUTH_HEADER,
      "Content-Type": "application/json",
      Accept: "application/json",
    });
    expectNoFilesystemAccess();
  });

  it("returns the authoritative empty project list from the backend", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { projects: [] }));

    const res = await invoke(projectsHandler, "GET");

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ projects: [] });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("reports a backend transport failure instead of an empty list", async () => {
    mockFetch.mockRejectedValue(new Error("backend down"));

    const res = await invoke(projectsHandler, "GET");

    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "Backend is unavailable",
      code: "BACKEND_UNAVAILABLE",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("reports malformed backend JSON instead of an empty list", async () => {
    mockFetch.mockResolvedValue(malformedResponse(200));

    const res = await invoke(projectsHandler, "GET");

    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "Backend is unavailable",
      code: "BACKEND_UNAVAILABLE",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("passes through an authorized backend 404 without local fallback", async () => {
    const backendError = { error: "Projects are unavailable" };
    mockFetch.mockResolvedValue(httpResponse(false, 404, backendError));

    const res = await invoke(projectsHandler, "GET");

    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual(backendError);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("creates a project by forwarding the authenticated POST body", async () => {
    const payload = { name: "New" };
    const backendProject = {
      id: "server-project-9",
      name: "New",
      tasks: [],
      createdAt: "backend-created-at",
    };
    mockFetch.mockResolvedValue(httpResponse(true, 201, { project: backendProject }));

    const res = await invoke(projectsHandler, "POST", { body: payload });

    expect(res._getStatusCode()).toBe(201);
    expect(res._getJSONData()).toEqual({ project: backendProject });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${BACKEND_URL}/api/v1/projects`);
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify(payload));
    expect(init.headers).toEqual({
      Authorization: AUTH_HEADER,
      "Content-Type": "application/json",
      Accept: "application/json",
    });
    expectNoFilesystemAccess();
  });

  it("does not apply client project changes locally when the backend rejects them", async () => {
    const payload = { name: "Client rename" };
    const backendError = { error: "Project name already exists", code: "CONFLICT" };
    mockFetch.mockResolvedValue(httpResponse(false, 409, backendError));

    const res = await invoke(projectsHandler, "POST", { body: payload });

    expect(res._getStatusCode()).toBe(409);
    expect(res._getJSONData()).toEqual(backendError);
    expect(mockFetch.mock.calls[0][1].body).toBe(JSON.stringify(payload));
    expectNoFilesystemAccess();
  });

  it("rejects anonymous project requests before dispatch", async () => {
    const res = await invoke(projectsHandler, "GET", { headers: {} });

    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Authentication required" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("rejects malformed authorization before dispatch", async () => {
    const res = await invoke(projectsHandler, "POST", {
      body: { name: "New" },
      headers: { authorization: "Token not-a-bearer" },
    });

    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Authentication required" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("does not retry a POST whose transport confirmation was lost", async () => {
    mockFetch.mockRejectedValue(new Error("socket hang up"));

    const res = await invoke(projectsHandler, "POST", { body: { name: "New" } });

    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "The operation could not be confirmed",
      code: "EFFECT_UNKNOWN",
      effect: "unknown",
      replay: "do_not_repeat",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("rejects other methods with 405 before dispatch", async () => {
    const res = await invoke(projectsHandler, "PUT", { body: { name: "New" } });

    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });
});

describe("pages/api/v1/projects/[id]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    installBackendTransport();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    restoreBackendTransport();
  });

  it("forwards an authenticated PUT with the encoded id, method and body", async () => {
    const payload = { name: "Updated" };
    const backendProject = {
      id: "project/with space",
      name: "Updated",
      tasks: [],
    };
    mockFetch.mockResolvedValue(httpResponse(true, 200, { project: backendProject }));

    const res = await invoke(projectIdHandler, "PUT", {
      query: { id: "project/with space" },
      body: payload,
    });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ project: backendProject });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${BACKEND_URL}/api/v1/projects/project%2Fwith%20space`);
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify(payload));
    expect(init.headers).toEqual({
      Authorization: AUTH_HEADER,
      "Content-Type": "application/json",
      Accept: "application/json",
    });
    expectNoFilesystemAccess();
  });

  it("returns the backend project instead of applying client changes locally", async () => {
    const payload = { name: "Client rename" };
    const backendProject = {
      id: "project_x",
      name: "Server kept this",
      tasks: [{ id: "t1" }],
    };
    mockFetch.mockResolvedValue(httpResponse(true, 200, { project: backendProject }));

    const res = await invoke(projectIdHandler, "PUT", {
      query: { id: "project_x" },
      body: payload,
    });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ project: backendProject });
    expect(mockFetch.mock.calls[0][1].body).toBe(JSON.stringify(payload));
    expect(mockWriteFileSync).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("passes through an authorized backend 404 without writing locally", async () => {
    const backendError = { error: "Project not found" };
    mockFetch.mockResolvedValue(httpResponse(false, 404, backendError));

    const res = await invoke(projectIdHandler, "PUT", {
      query: { id: "nope" },
      body: { name: "X" },
    });

    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual(backendError);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("passes through an authorized backend 409 without writing locally", async () => {
    const backendError = { error: "Project was changed", code: "STALE_PROJECT" };
    mockFetch.mockResolvedValue(httpResponse(false, 409, backendError));

    const res = await invoke(projectIdHandler, "PUT", {
      query: { id: "project_x" },
      body: { name: "Updated" },
    });

    expect(res._getStatusCode()).toBe(409);
    expect(res._getJSONData()).toEqual(backendError);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("rejects anonymous PUT before dispatch", async () => {
    const res = await invoke(projectIdHandler, "PUT", {
      query: { id: "project_x" },
      body: { name: "Updated" },
      headers: {},
    });

    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Authentication required" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("does not replay a PUT when the transport confirmation is lost", async () => {
    mockFetch.mockRejectedValue(new Error("connection reset"));

    const res = await invoke(projectIdHandler, "PUT", {
      query: { id: "project_x" },
      body: { name: "Updated" },
    });

    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "The operation could not be confirmed",
      code: "EFFECT_UNKNOWN",
      effect: "unknown",
      replay: "do_not_repeat",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("turns a malformed backend readback into an unknown-effect response", async () => {
    mockFetch.mockResolvedValue(malformedResponse(200));

    const res = await invoke(projectIdHandler, "PUT", {
      query: { id: "project_x" },
      body: { name: "Updated" },
    });

    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "The operation could not be confirmed",
      code: "EFFECT_UNKNOWN",
      effect: "unknown",
      replay: "do_not_repeat",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("rejects traversal record ids before dispatch", async () => {
    const res = await invoke(projectIdHandler, "PUT", {
      query: { id: ".." },
      body: { name: "Updated" },
    });

    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Invalid record id" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("rejects non-PUT with 405 before dispatch", async () => {
    const res = await invoke(projectIdHandler, "GET", { query: { id: "x" } });

    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });
});

describe("pages/api/v1/tasks", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    installBackendTransport();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    restoreBackendTransport();
  });

  it("lists tasks from the authenticated backend without local files", async () => {
    const tasks = [
      { id: "1", title: "First", status: "todo" },
      { id: "2", title: "Second", status: "in-progress" },
    ];
    mockFetch.mockResolvedValue(httpResponse(true, 200, { tasks }));

    const res = await invoke(tasksHandler, "GET", {
      query: { limit: "10", id: "ignored" },
    });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ tasks });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    // Only [id] routes explicitly remove their consumed path parameter.
    expect(url).toBe(`${BACKEND_URL}/api/v1/tasks?limit=10&id=ignored`);
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
    expect(init.headers).toEqual({
      Authorization: AUTH_HEADER,
      "Content-Type": "application/json",
      Accept: "application/json",
    });
    expectNoFilesystemAccess();
  });

  it("reports a backend transport failure instead of an empty task list", async () => {
    mockFetch.mockRejectedValue(new Error("backend down"));

    const res = await invoke(tasksHandler, "GET");

    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "Backend is unavailable",
      code: "BACKEND_UNAVAILABLE",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("reports malformed backend JSON instead of an empty task list", async () => {
    mockFetch.mockResolvedValue(malformedResponse(200));

    const res = await invoke(tasksHandler, "GET");

    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "Backend is unavailable",
      code: "BACKEND_UNAVAILABLE",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("forwards an authenticated POST and returns backend-owned task material", async () => {
    const payload = { title: "T", dueDate: "2026-09-01" };
    const backendTask = {
      id: "server-task-1",
      title: "T",
      dueDate: "2026-09-01",
      createdAt: "backend-created-at",
      updatedAt: "backend-updated-at",
    };
    mockFetch.mockResolvedValue(httpResponse(true, 201, { task: backendTask }));

    const res = await invoke(tasksHandler, "POST", { body: payload });

    expect(res._getStatusCode()).toBe(201);
    expect(res._getJSONData()).toEqual({ task: backendTask });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${BACKEND_URL}/api/v1/tasks`);
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify(payload));
    expect(init.headers).toEqual({
      Authorization: AUTH_HEADER,
      "Content-Type": "application/json",
      Accept: "application/json",
    });
    expectNoFilesystemAccess();
  });

  it("does not invent a local dueDate when the client omits one", async () => {
    const payload = { title: "T" };
    const backendTask = {
      id: "server-task-2",
      title: "T",
      dueDate: "backend-default-due-date",
      createdAt: "backend-created-at",
      updatedAt: "backend-created-at",
    };
    mockFetch.mockResolvedValue(httpResponse(true, 201, { task: backendTask }));

    const res = await invoke(tasksHandler, "POST", { body: payload });

    expect(res._getStatusCode()).toBe(201);
    expect(res._getJSONData()).toEqual({ task: backendTask });
    expect(mockFetch.mock.calls[0][1].body).toBe(JSON.stringify({ title: "T" }));
    expectNoFilesystemAccess();
  });

  it("passes through an authorized backend 409 without local mutation", async () => {
    const backendError = { error: "Task was changed", code: "STALE_TASK" };
    mockFetch.mockResolvedValue(httpResponse(false, 409, backendError));

    const res = await invoke(tasksHandler, "POST", { body: { title: "T" } });

    expect(res._getStatusCode()).toBe(409);
    expect(res._getJSONData()).toEqual(backendError);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("rejects anonymous task creation before dispatch", async () => {
    const res = await invoke(tasksHandler, "POST", {
      body: { title: "T" },
      headers: {},
    });

    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Authentication required" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("does not replay a POST when the transport confirmation is lost", async () => {
    mockFetch.mockRejectedValue(new Error("socket hang up"));

    const res = await invoke(tasksHandler, "POST", { body: { title: "T" } });

    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "The operation could not be confirmed",
      code: "EFFECT_UNKNOWN",
      effect: "unknown",
      replay: "do_not_repeat",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expectNoFilesystemAccess();
  });

  it("rejects other methods with 405 before dispatch", async () => {
    const res = await invoke(tasksHandler, "DELETE");

    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
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
