import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/xero/health";

const mockFetch = jest.fn();

const httpResponse = (ok: boolean, status: number, data: any, statusText = ""): any => ({
  ok,
  status,
  statusText,
  json: async () => data,
  text: async () => (typeof data === "string" ? data : JSON.stringify(data)),
});

describe("pages/api/integrations/xero/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-GET methods with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns healthy 200 when the status check succeeds", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { status: "ok" }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.backend).toBe("connected");
    expect(body.connected_count).toBe(4);
    expect(body.total_services).toBe(4);
    expect(body.version).toBe("2.0.0");
    expect(body.services.api.status).toBe("healthy");
    expect(body.services.api.response_time).toEqual(expect.any(Number));
    expect(body.services.api.error).toBeUndefined();
    expect(typeof body.timestamp).toBe("string");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/xero/status",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("reports degraded services and 503 when the backend responds with an error", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 500, "upstream exploded", "Internal Server Error"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.connected_count).toBe(0);
    expect(body.services.api.status).toBe("unhealthy");
    expect(body.services.api.error).toBe("upstream exploded");
    expect(body.services.accounting.status).toBe("degraded");
  });

  it("falls back to statusText when the error body is empty", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 503, "", "Service Unavailable"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData().services.api.error).toBe("Service Unavailable");
  });

  it("falls back to 'Unknown error' when text() and statusText are empty", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 503, "", ""));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getJSONData().services.api.error).toBe("Unknown error");
  });

  it("returns 503 with reason message when the fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.backend).toBe("connected");
    expect(body.error).toBeUndefined();
    expect(body.services.api.error).toBe("ECONNREFUSED");
    expect(body.services.api.response_time).toBeUndefined();
  });
});
