import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/accounting/export";

const mockFetch = jest.fn();

const csvBytes = Uint8Array.from([104, 101, 97, 100, 101, 114]); // "header"

const csvResponse = () => ({
  ok: true,
  status: 200,
  headers: {
    get: (name: string) => (name.toLowerCase() === "content-type" ? "text/csv" : null),
  },
  text: async () => "header",
  json: async () => ({}),
  blob: async () => ({
    arrayBuffer: async () => csvBytes.buffer,
  }),
});

const jsonResponse = (body: any, status = 200) => ({
  ok: status < 400,
  status,
  headers: {
    get: (name: string) =>
      name.toLowerCase() === "content-type" ? "application/json" : null,
  },
  text: async () => JSON.stringify(body),
  json: async () => body,
  blob: async () => ({ arrayBuffer: async () => new ArrayBuffer(0) }),
});

describe("pages/api/accounting/export", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.NEXT_PUBLIC_API_URL;
    mockFetch.mockResolvedValue(csvResponse());
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (
    query: any = {},
    opts: { method?: RequestMethod; headers?: any } = {},
  ) => {
    const { req, res } = createMocks({
      method: opts.method ?? "GET",
      query,
      headers: opts.headers,
    }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke({ type: "gl" }, { method: "POST" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when type is missing", async () => {
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: 'Invalid export type. Must be "gl" or "tb".',
    });
  });

  it("returns 400 for an unsupported export type", async () => {
    const res = await invoke({ type: "pl" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: 'Invalid export type. Must be "gl" or "tb".',
    });
  });

  it("streams the GL CSV export with attachment headers", async () => {
    const res = await invoke({ type: "gl" }, { headers: { authorization: "Bearer tok" } });
    expect(res._getStatusCode()).toBe(200);
    expect(res.getHeader("Content-Type")).toBe("text/csv");
    expect(res.getHeader("Content-Disposition")).toBe(
      "attachment; filename=general_ledger_default.csv",
    );
    // node-mocks-http keeps a Buffer passed to send() in _data verbatim.
    expect(res._getData().toString()).toBe("header");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/ai-accounting/export/gl?workspace_id=default",
      { headers: { Authorization: "Bearer tok" } },
    );
  });

  it("returns the trial balance export as pretty-printed JSON", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ accounts: [{ name: "Cash", balance: 10 }] }),
    );
    const res = await invoke({ type: "tb" });
    expect(res._getStatusCode()).toBe(200);
    expect(res.getHeader("Content-Type")).toBe("application/json");
    expect(res.getHeader("Content-Disposition")).toBe(
      "attachment; filename=trial_balance_default.json",
    );
    expect(res._getData()).toBe(
      JSON.stringify({ accounts: [{ name: "Cash", balance: 10 }] }, null, 2),
    );
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/ai-accounting/export/trial-balance?workspace_id=default",
    );
  });

  it("omits the Authorization header when the request has none", async () => {
    await invoke({ type: "gl" });
    expect(mockFetch.mock.calls[0][1]).toEqual({ headers: {} });
  });

  it("passes the backend failure status through", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      headers: { get: () => null },
      text: async () => "upstream unavailable",
      json: async () => ({}),
      blob: async () => ({ arrayBuffer: async () => new ArrayBuffer(0) }),
    });
    const res = await invoke({ type: "gl" });
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({ error: "Failed to export gl" });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 500 when the backend request throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke({ type: "tb" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal server error during export",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
