const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/azure/health";

describe("pages/api/integrations/azure/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    return res;
  };

  it("reports healthy with both services connected when the backend is up", async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.backend).toBe("connected");
    expect(body.services.oauth).toEqual({ status: "healthy", connected: true });
    expect(body.services.infrastructure).toEqual({
      status: "healthy",
      connected: true,
    });
    expect(body.connected_count).toBe(2);
    expect(body.total_services).toBe(2);
    expect(typeof body.timestamp).toBe("string");
    expect(mockFetch).toHaveBeenCalledWith("http://127.0.0.1:8000/health", { headers: {} });
  });

  it("reports disconnected when the backend infra check fails", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("disconnected");
    expect(body.services.oauth).toEqual({ status: "unknown", connected: false });
    expect(body.services.infrastructure).toEqual({
      status: "unhealthy",
      connected: false,
    });
    expect(body.connected_count).toBe(0);
    expect(body.total_services).toBe(2);
  });

  it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:6000";
    mockFetch.mockResolvedValue({ ok: true });
    await invoke();
    expect(mockFetch).toHaveBeenCalledWith("http://python:6000/health", { headers: {} });
  });

  it("returns 503 unhealthy when the health fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("backend unreachable"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      status: "unhealthy",
      error: "Azure services unavailable",
    });
  });
});
