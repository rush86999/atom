const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/gmail/memory/search";

describe("pages/api/integrations/gmail/memory/search", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://memory.test";
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (method: any = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET", { query: "invoices" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the search query is missing", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Search query is required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the query is an empty string", async () => {
    const res = await invoke("POST", { query: "" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Search query is required" });
  });

  it("forwards the search to the memory service and returns results", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        data: [{ id: "m1", snippet: "invoice from Acme" }],
        message: "done",
      }),
    });
    const res = await invoke("POST", { query: "invoice acme", limit: 5 });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: [{ id: "m1", snippet: "invoice from Acme" }],
      message: "done",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://memory.test/api/memory/ingestion/search?query=invoice%20acme&app_id=gmail&limit=5",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("defaults the limit to 10 and message when the backend omits them", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke("POST", { query: "receipts" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: [],
      message: "Search completed successfully",
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://memory.test/api/memory/ingestion/search?query=receipts&app_id=gmail&limit=10",
    );
  });

  it("uses the default backend URL when the env var is unset", async () => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke("POST", { query: "anything" });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch.mock.calls[0][0]).toContain(
      "http://127.0.0.1:8000/api/memory/ingestion/search",
    );
  });

  it("encodes special characters in the query string", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    await invoke("POST", { query: "q&a=b +c" });
    expect(mockFetch.mock.calls[0][0]).toContain(
      "query=q%26a%3Db%20%2Bc",
    );
  });

  it("passes through the backend status and details on failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      text: async () => "service unavailable",
    });
    const res = await invoke("POST", { query: "invoice" });
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "Failed to search Gmail memory",
      details: "service unavailable",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Gmail memory search error:",
      "service unavailable",
    );
  });

  it("returns 500 when the memory service fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const res = await invoke("POST", { query: "invoice" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal server error",
      details: "connection refused",
    });
  });

  it("returns 500 with Unknown error when a non-Error is thrown", async () => {
    mockFetch.mockRejectedValue("just a string");
    const res = await invoke("POST", { query: "invoice" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal server error",
      details: "Unknown error",
    });
  });
});
