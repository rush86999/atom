const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/accounting/[id]";

function backendJson(body: any, ok = true, status = 200): any {
  return { ok, status, json: async () => body };
}

function backendError(status: number, text: string): any {
  return { ok: false, status, text: async () => text };
}

describe("pages/api/accounting/[id]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (
    method: any,
    options: { id?: any; body?: any; auth?: string | null } = {},
  ) => {
    const { body } = options;
    const id = "id" in options ? options.id : "txn-1";
    const auth = "auth" in options ? options.auth : "Bearer tok-123";
    const { req, res } = createMocks({
      method,
      query: id === undefined ? {} : { id },
      body,
      headers: auth ? { authorization: auth } : {},
    }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 400 when the transaction id is missing", async () => {
    const res = await invoke("PUT", { id: undefined });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Transaction ID is required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("proxies a successful PUT and returns the backend payload", async () => {
    mockFetch.mockResolvedValue(backendJson({ id: "txn-1", amount: 42 }));
    const res = await invoke("PUT", { body: { amount: 42 } });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ id: "txn-1", amount: 42 });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/ai-accounting/transactions/txn-1");
    expect(init.method).toBe("PUT");
    expect(init.headers.Authorization).toBe("Bearer tok-123");
    expect(JSON.parse(init.body)).toEqual({ amount: 42 });
  });

  it("omits the Authorization header on PUT when the request had none", async () => {
    mockFetch.mockResolvedValue(backendJson({ ok: true }));
    await invoke("PUT", { body: {}, auth: undefined });
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("passes through the backend status and text on a failed PUT", async () => {
    mockFetch.mockResolvedValue(backendError(404, "Transaction not found"));
    const res = await invoke("PUT", { body: {} });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "Transaction not found" });
  });

  it("returns 500 when the PUT request fails", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("PUT", { body: {} });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to update transaction" });
  });

  it("proxies a successful DELETE and returns the backend payload", async () => {
    mockFetch.mockResolvedValue(backendJson({ success: true }));
    const res = await invoke("DELETE", { id: "txn-9" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/ai-accounting/transactions/txn-9");
    expect(init.method).toBe("DELETE");
    expect(init.headers.Authorization).toBe("Bearer tok-123");
  });

  it("omits the Authorization header on DELETE when the request had none", async () => {
    mockFetch.mockResolvedValue(backendJson({ success: true }));
    await invoke("DELETE", { auth: undefined });
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("passes through the backend status and text on a failed DELETE", async () => {
    mockFetch.mockResolvedValue(backendError(409, "Already reconciled"));
    const res = await invoke("DELETE");
    expect(res._getStatusCode()).toBe(409);
    expect(res._getJSONData()).toEqual({ error: "Already reconciled" });
  });

  it("returns 500 when the DELETE request fails", async () => {
    mockFetch.mockRejectedValue(new Error("socket hang up"));
    const res = await invoke("DELETE");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to delete transaction" });
  });

  it("rejects unsupported methods with 405", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
