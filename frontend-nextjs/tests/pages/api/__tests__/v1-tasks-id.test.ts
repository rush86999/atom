const mockFetch = jest.fn();
const mockExistsSync = jest.fn();
const mockMkdirSync = jest.fn();
const mockReadFileSync = jest.fn();
const mockWriteFileSync = jest.fn();
jest.mock("fs", () => ({
  existsSync: mockExistsSync,
  mkdirSync: mockMkdirSync,
  readFileSync: mockReadFileSync,
  writeFileSync: mockWriteFileSync,
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/v1/tasks/[id]";

const BACKEND_URL = "http://backend.test";
const AUTH_HEADER = "Bearer controlled-task-id-token";

const httpResponse = (status: number, data: unknown, jsonFails = false): any => ({
  ok: status >= 200 && status < 300,
  status,
  statusText: "",
  json: async () => {
    if (jsonFails) throw new SyntaxError("Unexpected token < in JSON");
    return data;
  },
  text: async () => (typeof data === "string" ? data : JSON.stringify(data)),
});

const originalFetch = (global as any).fetch;
const originalBackendUrl = process.env.BACKEND_URL;
const originalPythonBackendUrl = process.env.PYTHON_BACKEND_URL;
const originalNextPublicApiUrl = process.env.NEXT_PUBLIC_API_URL;

const restoreEnvironment = () => {
  if (originalFetch === undefined) delete (global as any).fetch;
  else (global as any).fetch = originalFetch;
  if (originalBackendUrl === undefined) delete process.env.BACKEND_URL;
  else process.env.BACKEND_URL = originalBackendUrl;
  if (originalPythonBackendUrl === undefined) delete process.env.PYTHON_BACKEND_URL;
  else process.env.PYTHON_BACKEND_URL = originalPythonBackendUrl;
  if (originalNextPublicApiUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
  else process.env.NEXT_PUBLIC_API_URL = originalNextPublicApiUrl;
};

describe("pages/api/v1/tasks/[id]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.BACKEND_URL = BACKEND_URL;
    delete process.env.PYTHON_BACKEND_URL;
    delete process.env.NEXT_PUBLIC_API_URL;
    (global as any).fetch = mockFetch;
  });

  afterEach(() => {
    restoreEnvironment();
  });

  const invoke = async (
    method: string,
    query: Record<string, any> = { id: "1" },
    body?: any,
    headers: Record<string, string> = { authorization: AUTH_HEADER },
  ) => {
    const { req, res } = createMocks({ method, query, body, headers }) as any;
    req.body = body;
    await handler(req, res);
    return res;
  };

  const expectNoFilesystemAccess = () => {
    expect(mockExistsSync).not.toHaveBeenCalled();
    expect(mockMkdirSync).not.toHaveBeenCalled();
    expect(mockReadFileSync).not.toHaveBeenCalled();
    expect(mockWriteFileSync).not.toHaveBeenCalled();
  };

  it("forwards an authenticated PUT with the exact id, method and body", async () => {
    const payload = { title: "Updated", status: "done" };
    const backendTask = {
      id: "1",
      title: "Updated",
      status: "done",
      updatedAt: "2026-11-09T00:00:00.000Z",
    };
    mockFetch.mockResolvedValue(httpResponse(200, { task: backendTask }));

    const res = await invoke("PUT", { id: "1" }, payload);

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ task: backendTask });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${BACKEND_URL}/api/v1/tasks/1`);
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify(payload));
    expect(init.headers).toEqual({
      Authorization: AUTH_HEADER,
      "Content-Type": "application/json",
      Accept: "application/json",
    });
    expect(init.redirect).toBe("error");
    expectNoFilesystemAccess();
  });

  it("encodes a dynamic task id and forwards DELETE without a body", async () => {
    mockFetch.mockResolvedValue(httpResponse(200, { success: true }));

    const res = await invoke("DELETE", { id: "task/a b" });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${BACKEND_URL}/api/v1/tasks/task%2Fa%20b`);
    expect(init.method).toBe("DELETE");
    expect(init.body).toBeUndefined();
    expectNoFilesystemAccess();
  });

  it("passes through an authorized backend 404 without writing locally", async () => {
    const backendError = { error: "Task not found" };
    mockFetch.mockResolvedValue(httpResponse(404, backendError));

    const res = await invoke("PUT", { id: "999" }, { title: "Nope" });

    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual(backendError);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch.mock.calls[0][0]).toBe(`${BACKEND_URL}/api/v1/tasks/999`);
    expectNoFilesystemAccess();
  });

  it("passes through an authorized backend 409 without writing locally", async () => {
    const backendError = { error: "Task was changed", code: "STALE_TASK" };
    mockFetch.mockResolvedValue(httpResponse(409, backendError));

    const res = await invoke("DELETE", { id: "2" });

    expect(res._getStatusCode()).toBe(409);
    expect(res._getJSONData()).toEqual(backendError);
    expect(mockFetch.mock.calls[0][1].method).toBe("DELETE");
    expectNoFilesystemAccess();
  });

  it("returns the backend material instead of applying client changes locally", async () => {
    const payload = { title: "Client changed this" };
    const backendTask = { id: "1", title: "Server keeps this", status: "todo" };
    mockFetch.mockResolvedValue(httpResponse(200, { task: backendTask }));

    const res = await invoke("PUT", { id: "1" }, payload);

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ task: backendTask });
    expect(mockFetch.mock.calls[0][1].body).toBe(JSON.stringify(payload));
    expect(mockWriteFileSync).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("rejects anonymous PUT before dispatch", async () => {
    const res = await invoke("PUT", { id: "1" }, { title: "Updated" }, {});

    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Authentication required" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("rejects malformed authorization before dispatch", async () => {
    const res = await invoke("DELETE", { id: "1" }, undefined, {
      authorization: "Token not-a-bearer",
    });

    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Authentication required" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("reports an unknown effect when a PUT loses its transport confirmation", async () => {
    mockFetch.mockRejectedValue(new Error("socket hang up"));

    const res = await invoke("PUT", { id: "1" }, { title: "Updated" });

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

  it("does not replay a DELETE when the transport confirmation is lost", async () => {
    mockFetch.mockRejectedValue(new Error("connection reset"));

    const res = await invoke("DELETE", { id: "2" });

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

  it("treats a malformed backend readback on PUT as an unknown effect", async () => {
    mockFetch.mockResolvedValue(httpResponse(200, {}, true));

    const res = await invoke("PUT", { id: "1" }, { title: "Updated" });

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

  it("rejects unsupported methods with 405 before dispatch", async () => {
    const res = await invoke("GET", { id: "1" });

    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });

  it("rejects traversal record ids before dispatch", async () => {
    const res = await invoke("PUT", { id: ".." }, { title: "Updated" });

    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Invalid record id" });
    expect(mockFetch).not.toHaveBeenCalled();
    expectNoFilesystemAccess();
  });
});
