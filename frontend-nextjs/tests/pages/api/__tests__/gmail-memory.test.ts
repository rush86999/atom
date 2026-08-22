const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import syncHandler from "@/pages/api/integrations/gmail/memory/sync";
import statsHandler from "@/pages/api/integrations/gmail/memory/stats";

const okResponse = (data: any): any => ({
  ok: true,
  status: 200,
  json: async () => data,
});

const failingResponse = (status: number, text: string): any => ({
  ok: false,
  status,
  json: async () => ({}),
  text: async () => text,
});

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
});

describe("pages/api/integrations/gmail/memory/sync", () => {
  const invoke = async (body?: any, method = "POST"): Promise<any> => {
    const { req, res } = createMocks({ method, body }) as any;
    await syncHandler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("starts the ingestion stream and returns backend data", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ data: { started: true }, message: "stream started" }),
    );
    const res = await invoke({ force_full_sync: true, max_messages: 50 });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: { started: true },
      message: "stream started",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/memory/ingestion/stream/start/gmail",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      },
    );
  });

  it("defaults data and message when the backend omits them", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: {},
      message: "Memory sync completed successfully",
    });
  });

  it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5058";
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke({});
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://python:5058/api/memory/ingestion/stream/start/gmail",
    );
  });

  it("forwards the backend failure status and details", async () => {
    mockFetch.mockResolvedValue(failingResponse(503, "lancedb unavailable"));
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "Failed to sync Gmail memory",
      details: "lancedb unavailable",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 500 with the error message when the fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal server error",
      details: "connection refused",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("reports Unknown error for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke({});
    expect(res._getJSONData()).toEqual({
      error: "Internal server error",
      details: "Unknown error",
    });
  });
});

describe("pages/api/integrations/gmail/memory/stats", () => {
  const invoke = async (method = "GET"): Promise<any> => {
    const { req, res } = createMocks({ method }) as any;
    await statsHandler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("retrieves memory stats from the backend", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ data: { vectors: 42 }, message: "stats ok" }),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: { vectors: 42 },
      message: "stats ok",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/memory/ingestion/memory/stats",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("defaults data and message when the backend omits them", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: {},
      message: "Memory stats retrieved successfully",
    });
  });

  it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5058";
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke();
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://python:5058/api/memory/ingestion/memory/stats",
    );
  });

  it("forwards the backend failure status and details", async () => {
    mockFetch.mockResolvedValue(failingResponse(500, "stats unavailable"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to get Gmail memory stats",
      details: "stats unavailable",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 500 with the error message when the fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("socket hang up"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal server error",
      details: "socket hang up",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("reports Unknown error for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("nope");
    const res = await invoke();
    expect(res._getJSONData()).toEqual({
      error: "Internal server error",
      details: "Unknown error",
    });
  });
});
