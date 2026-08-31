const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/salesforce/health";

function apiResponse(ok: boolean, status = 200, text = ""): any {
  return { ok, status, json: async () => ({}), text: async () => text };
}

describe("pages/api/integrations/salesforce/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "GET") => {
    const { req, res } = createMocks({ method: method as RequestMethod }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("reports healthy when api and auth checks pass", async () => {
    mockFetch.mockResolvedValue(apiResponse(true));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.backend).toBe("connected");
    expect(body.services.api.status).toBe("healthy");
    expect(body.services.auth.status).toBe("healthy");
    expect(body.services.sobjects.status).toBe("healthy");
    expect(body.services.soql.status).toBe("healthy");
    expect(body.connected_count).toBe(4);
    expect(body.total_services).toBe(4);
    expect(body.version).toBe("2.0.0");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/salesforce/health"),
      expect.objectContaining({ method: "GET" }),
    );
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/salesforce/status"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("reports degraded when the api check fails but auth passes", async () => {
    mockFetch
      .mockResolvedValueOnce(apiResponse(false, 503, "salesforce api down"))
      .mockResolvedValueOnce(apiResponse(true));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("degraded");
    expect(body.services.api.status).toBe("unhealthy");
    expect(body.services.api.connected).toBe(false);
    expect(body.services.api.error).toBe("salesforce api down");
    expect(body.services.auth.status).toBe("healthy");
    expect(body.services.sobjects.status).toBe("healthy");
    expect(body.services.soql.status).toBe("healthy");
    expect(body.connected_count).toBe(3);
  });

  it("reports degraded when the auth check is rejected", async () => {
    mockFetch
      .mockResolvedValueOnce(apiResponse(true))
      .mockRejectedValueOnce(new Error("auth token expired"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("degraded");
    expect(body.services.api.status).toBe("healthy");
    expect(body.services.auth.status).toBe("unhealthy");
    expect(body.services.auth.error).toBe("auth token expired");
    expect(body.connected_count).toBe(3);
  });

  it("keeps sobjects/soql placeholders healthy even when both real checks fail", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("degraded");
    expect(body.connected_count).toBe(2);
    expect(body.services.api.status).toBe("unhealthy");
    expect(body.services.auth.status).toBe("unhealthy");
    expect(body.services.sobjects.status).toBe("healthy");
    expect(body.services.soql.status).toBe("healthy");
  });
});
