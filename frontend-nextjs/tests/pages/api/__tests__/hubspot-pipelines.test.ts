const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/hubspot/pipelines";

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/hubspot/pipelines", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (method: RequestMethod = "GET", query: any = {}, body?: any) => {
    const { req, res } = createMocks({ method, query, body }) as any;
    await handler(req, res);
    return res;
  };

  it("proxies a plain GET list request to the backend", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(true, 200, { results: [{ id: "pl-1" }] }),
    );
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ results: [{ id: "pl-1" }] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/pipelines",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        body: undefined,
      },
    );
  });

  it("appends the id path segment for a single id", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, { id: "pl-1" }));
    await invoke("GET", { id: "pl-1" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/pipelines/pl-1",
      expect.anything(),
    );
  });

  it("ignores array ids and forwards remaining query params", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET", { id: ["1", "2"], limit: "5" });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/hubspot/pipelines");
    expect(url).not.toMatch(/\/1(\?|$)/);
    expect(url).not.toContain("id=");
    expect(url).toContain("limit=5");
  });

  it("sends the request body for non-GET methods", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 201, { id: "new" }));
    const res = await invoke("POST", {}, { label: "Sales pipeline" });
    expect(res._getStatusCode()).toBe(201);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/pipelines",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: "Sales pipeline" }),
      },
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:6000";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://python:6000/api/hubspot/pipelines",
      expect.anything(),
    );
  });

  it("mirrors backend error status and payload", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(false, 404, { error: "pipeline not found" }),
    );
    const res = await invoke("GET", { id: "missing" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "pipeline not found" });
  });

  it("returns 500 with the error message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch HubSpot pipelines",
      message: "network down",
    });
  });

  it("falls back to 'Unknown error' for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch HubSpot pipelines",
      message: "Unknown error",
    });
  });
});
