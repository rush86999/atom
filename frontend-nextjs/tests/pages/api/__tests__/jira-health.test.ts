const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/jira/health";

function apiResponse(
  ok: boolean,
  status = 200,
  text = "",
  statusText = "Status Text",
): any {
  return { ok, status, statusText, json: async () => ({}), text: async () => text };
}

describe("pages/api/integrations/jira/health", () => {
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
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("reports healthy when the Jira status check passes", async () => {
    mockFetch.mockResolvedValue(apiResponse(true));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.backend).toBe("connected");
    expect(Object.keys(body.services)).toEqual([
      "api",
      "auth",
      "issues",
      "projects",
    ]);
    expect(body.services.api.connected).toBe(true);
    expect(body.services.api.error).toBeUndefined();
    expect(typeof body.services.api.response_time).toBe("number");
    expect(body.services.issues.status).toBe("healthy");
    expect(body.services.projects.status).toBe("healthy");
    expect(body.connected_count).toBe(4);
    expect(body.total_services).toBe(4);
    expect(body.version).toBe("2.0.0");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/jira/status"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("reports unhealthy with the rejection reason when the fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("jira unreachable"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.services.api.connected).toBe(false);
    expect(body.services.api.error).toBe("jira unreachable");
    expect(body.services.api.response_time).toBeUndefined();
    expect(body.services.issues.status).toBe("degraded");
    expect(body.services.projects.status).toBe("degraded");
    expect(body.connected_count).toBe(0);
  });

  it("reports unhealthy with the response text when the status check fails", async () => {
    mockFetch.mockResolvedValue(apiResponse(false, 503, "jira down"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.services.api.error).toBe("jira down");
    expect(body.connected_count).toBe(0);
  });

  it("falls back to statusText when the error body is empty", async () => {
    mockFetch.mockResolvedValue(apiResponse(false, 500, "", "Bad Gateway"));
    const res = await invoke();
    expect(res._getJSONData().services.api.error).toBe("Bad Gateway");
  });

  it("falls back to 'Unknown error' when the body is unreadable and statusText empty", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "",
      json: async () => ({}),
      text: async () => {
        throw new Error("read failed");
      },
    });
    const res = await invoke();
    expect(res._getJSONData().services.api.error).toBe("Unknown error");
  });

  it("returns 503 with a disconnected backend when a synchronous error escapes", async () => {
    mockFetch.mockImplementation(() => {
      throw new Error("boom");
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.backend).toBe("disconnected");
    expect(body.error).toBe("Jira services unavailable");
    expect(typeof body.timestamp).toBe("string");
  });
});
