const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/linear/health";

function apiResponse(ok: boolean, status = 200, text = ""): any {
  return { ok, status, json: async () => ({}), text: async () => text };
}

describe("pages/api/integrations/linear/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method: RequestMethod = "GET") => {
    const { req, res } = createMocks({ method }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("reports healthy when status and teams checks pass", async () => {
    mockFetch.mockResolvedValue(apiResponse(true));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.backend).toBe("connected");
    expect(body.services.api.status).toBe("healthy");
    expect(body.services.auth.status).toBe("healthy");
    expect(body.services.issues.status).toBe("healthy");
    expect(body.services.teams.status).toBe("healthy");
    expect(body.connected_count).toBe(4);
    expect(body.total_services).toBe(4);
    expect(body.version).toBe("2.0.0");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/linear/status"),
      expect.objectContaining({ method: "GET" }),
    );
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/linear/teams/health"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("reports degraded with rejection reason when status check fails", async () => {
    mockFetch
      .mockRejectedValueOnce(new Error("linear api down"))
      .mockResolvedValueOnce(apiResponse(true));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("degraded");
    expect(body.services.api.status).toBe("unhealthy");
    expect(body.services.api.connected).toBe(false);
    expect(body.services.api.error).toBe("linear api down");
    expect(body.services.auth.status).toBe("unhealthy");
    expect(body.services.issues.status).toBe("degraded");
    expect(body.services.teams.status).toBe("healthy");
    expect(body.connected_count).toBe(1);
  });

  it("reports degraded with response text when the status check returns non-OK", async () => {
    mockFetch
      .mockResolvedValueOnce(apiResponse(false, 500, "status endpoint broken"))
      .mockResolvedValueOnce(apiResponse(true));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("degraded");
    expect(body.services.api.status).toBe("unhealthy");
    expect(body.services.api.error).toBe("status endpoint broken");
    expect(body.services.teams.status).toBe("healthy");
  });

  it("reports unhealthy with 503 when all checks fail", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.connected_count).toBe(0);
    expect(body.services.api.status).toBe("unhealthy");
    expect(body.services.teams.status).toBe("degraded");
  });
});
