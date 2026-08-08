const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/hubspot/health";

function apiResponse(ok: boolean, status = 200, text = ""): any {
  return { ok, status, json: async () => ({}), text: async () => text };
}

describe("pages/api/integrations/hubspot/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.USE_BRIDGE_SYSTEM;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "warn").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "GET") => {
    const { req, res } = createMocks({ method }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("reports healthy when direct endpoint checks pass", async () => {
    mockFetch.mockResolvedValue(apiResponse(true));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.backend).toBe("connected");
    expect(body.services.api.status).toBe("healthy");
    expect(body.services.api.connected).toBe(true);
    expect(body.services.auth.status).toBe("healthy");
    expect(body.services.webhooks.status).toBe("healthy");
    expect(body.connected_count).toBe(3);
    expect(body.total_services).toBe(3);
    expect(body.version).toBe("2.0.0");
    expect(typeof body.timestamp).toBe("string");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/hubspot/health"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("reports degraded with error details when the API check fails", async () => {
    mockFetch.mockResolvedValue(apiResponse(false, 503, "hubspot down"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("degraded");
    expect(body.services.api.status).toBe("unhealthy");
    expect(body.services.api.connected).toBe(false);
    expect(body.services.api.error).toBe("hubspot down");
    expect(body.services.auth.status).toBe("unhealthy");
    expect(body.services.auth.error).toBe("hubspot down");
    expect(body.services.webhooks.status).toBe("healthy");
    expect(body.connected_count).toBe(1);
  });

  it("reports degraded with a rejection reason when the auth check fails", async () => {
    mockFetch
      .mockResolvedValueOnce(apiResponse(true))
      .mockRejectedValueOnce(new Error("auth down"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("degraded");
    expect(body.services.api.status).toBe("healthy");
    expect(body.services.webhooks.status).toBe("healthy");
    expect(body.connected_count).toBe(2);
  });

  it("uses the bridge system when enabled and healthy", async () => {
    process.env.USE_BRIDGE_SYSTEM = "true";
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/bridge/health")) {
        return Promise.resolve(apiResponse(true));
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          integrations: {
            hubspot: {
              status: "active",
              last_check: "2026-08-01T00:00:00.000Z",
              available_endpoints: ["webhooks", "contacts"],
            },
          },
        }),
      });
    });
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.services.api.status).toBe("healthy");
    expect(body.services.api.last_check).toBe("2026-08-01T00:00:00.000Z");
    expect(body.services.webhooks.status).toBe("healthy");
    expect(body.services.webhooks.connected).toBe(true);
    expect(body.connected_count).toBe(3);
    const calledUrls = mockFetch.mock.calls.map((c: any) => c[0] as string);
    expect(calledUrls.some((u) => u.includes("/api/hubspot/health"))).toBe(false);
  });

  it("reports unhealthy with 503 when the bridge reports an inactive integration without webhooks", async () => {
    process.env.USE_BRIDGE_SYSTEM = "true";
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/bridge/health")) {
        return Promise.resolve(apiResponse(true));
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          integrations: {
            hubspot: {
              status: "inactive",
              error_message: "token expired",
              available_endpoints: [],
            },
          },
        }),
      });
    });
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.connected_count).toBe(0);
    expect(body.services.api.status).toBe("unhealthy");
    expect(body.services.api.error).toBe("token expired");
    expect(body.services.webhooks.status).toBe("degraded");
    expect(body.services.webhooks.error).toBe("Webhook endpoints not configured");
  });

  it("falls back to direct checks when the bridge is unavailable", async () => {
    process.env.USE_BRIDGE_SYSTEM = "true";
    mockFetch
      .mockRejectedValueOnce(new Error("bridge down"))
      .mockImplementation(() => Promise.resolve(apiResponse(true)));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    const calledUrls = mockFetch.mock.calls.map((c: any) => c[0] as string);
    expect(calledUrls.some((u) => u.includes("/api/bridge/health"))).toBe(true);
    expect(calledUrls.some((u) => u.includes("/api/hubspot/health"))).toBe(true);
  });
});
