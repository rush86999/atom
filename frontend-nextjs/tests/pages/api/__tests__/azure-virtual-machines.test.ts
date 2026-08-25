const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/azure/virtual-machines";

const jsonResponse = (status: number, data: any): any => ({
  ok: status < 400,
  status,
  json: async () => data,
});

describe("pages/api/integrations/azure/virtual-machines", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (options: { method?: string; query?: any; body?: any }) => {
    const { method = "GET", query, body } = options;
    const { req, res } = createMocks({ method, query, body }) as any;
    await handler(req, res);
    return res;
  };

  it("proxies a plain GET list request to the backend", async () => {
    mockFetch.mockResolvedValue(jsonResponse(200, [{ name: "vm-1" }]));
    const res = await invoke({ method: "GET" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual([{ name: "vm-1" }]);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/azure/virtual-machines");
    expect(init.method).toBe("GET");
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      "x-user-id": "current",
    });
    expect(init.body).toBeUndefined();
  });

  it("appends the id path segment for single-vm GET requests", async () => {
    mockFetch.mockResolvedValue(jsonResponse(200, { name: "vm-1" }));
    const res = await invoke({ method: "GET", query: { id: "vm-42" } });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/azure/virtual-machines/vm-42",
    );
  });

  it("ignores a non-string id (array query value)", async () => {
    mockFetch.mockResolvedValue(jsonResponse(200, []));
    await invoke({ method: "GET", query: { id: ["a", "b"] } });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/azure/virtual-machines",
    );
  });

  it("forwards extra query params as a query string", async () => {
    mockFetch.mockResolvedValue(jsonResponse(200, []));
    await invoke({
      method: "GET",
      query: { resourceGroup: "rg-1", status: "running" },
    });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url.startsWith("http://127.0.0.1:8000/api/azure/virtual-machines?")).toBe(
      true,
    );
    expect(url).toContain("resourceGroup=rg-1");
    expect(url).toContain("status=running");
  });

  it("combines an id path segment with query params", async () => {
    mockFetch.mockResolvedValue(jsonResponse(200, {}));
    await invoke({
      method: "GET",
      query: { id: "vm-9", expand: "instanceView" },
    });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("/api/azure/virtual-machines/vm-9?");
    expect(url).toContain("expand=instanceView");
  });

  it("sends a JSON body for non-GET methods", async () => {
    mockFetch.mockResolvedValue(jsonResponse(201, { created: true }));
    const res = await invoke({
      method: "POST",
      body: { name: "new-vm", location: "eastus" },
    });
    expect(res._getStatusCode()).toBe(201);
    expect(res._getJSONData()).toEqual({ created: true });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/azure/virtual-machines");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "new-vm", location: "eastus" }));
  });

  it("honors PYTHON_API_SERVICE_BASE_URL when configured", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python-backend:1234";
    mockFetch.mockResolvedValue(jsonResponse(200, []));
    await invoke({ method: "GET" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://python-backend:1234/api/azure/virtual-machines",
    );
  });

  it("mirrors a backend error status and body", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(404, { error: "Virtual machine not found" }),
    );
    const res = await invoke({ method: "GET", query: { id: "missing" } });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "Virtual machine not found" });
  });

  it("returns 500 with the error message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("backend unreachable"));
    const res = await invoke({ method: "GET" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Azure virtual machines",
      message: "backend unreachable",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("falls back to 'Unknown error' for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("just a string");
    const res = await invoke({ method: "GET" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Azure virtual machines",
      message: "Unknown error",
    });
  });

  it("returns 500 when the backend response body is not valid JSON", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new Error("invalid json");
      },
    });
    const res = await invoke({ method: "GET" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().error).toBe("Failed to fetch Azure virtual machines");
  });
});
