const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/slack/health";

function apiResponse(
  ok: boolean,
  status = 200,
  text = "",
  statusText = "Status Text",
): any {
  return { ok, status, statusText, json: async () => ({}), text: async () => text };
}

describe("pages/api/integrations/slack/health", () => {
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

  it("reports healthy when the Slack status check passes", async () => {
    mockFetch.mockResolvedValue(apiResponse(true));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.backend).toBe("connected");
    expect(Object.keys(body.services)).toEqual([
      "auth",
      "messaging",
      "events",
      "webhooks",
    ]);
    expect(body.services.auth.connected).toBe(true);
    expect(body.services.auth.error).toBeUndefined();
    expect(typeof body.services.auth.response_time).toBe("number");
    expect(body.services.messaging.status).toBe("healthy");
    expect(body.services.events.status).toBe("healthy");
    expect(body.services.webhooks.status).toBe("healthy");
    expect(body.connected_count).toBe(4);
    expect(body.total_services).toBe(4);
    expect(body.version).toBe("2.0.0");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/slack/status"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("reports unhealthy with the rejection reason when the fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("slack unreachable"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.services.auth.connected).toBe(false);
    expect(body.services.auth.error).toBe("slack unreachable");
    expect(body.services.auth.response_time).toBeUndefined();
    expect(body.services.messaging.status).toBe("degraded");
    expect(body.services.webhooks.status).toBe("degraded");
    expect(body.connected_count).toBe(0);
  });

  it("reports unhealthy with the response text when the status check fails", async () => {
    mockFetch.mockResolvedValue(apiResponse(false, 503, "slack down"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    const body = res._getJSONData();
    expect(body.status).toBe("unhealthy");
    expect(body.services.auth.error).toBe("slack down");
    expect(body.connected_count).toBe(0);
  });

  it("falls back to statusText when the error body is empty", async () => {
    mockFetch.mockResolvedValue(apiResponse(false, 500, "", "Internal Server Error"));
    const res = await invoke();
    expect(res._getJSONData().services.auth.error).toBe("Internal Server Error");
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
    expect(res._getJSONData().services.auth.error).toBe("Unknown error");
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
    expect(body.error).toBe("Slack services unavailable");
    expect(typeof body.timestamp).toBe("string");
  });
});
