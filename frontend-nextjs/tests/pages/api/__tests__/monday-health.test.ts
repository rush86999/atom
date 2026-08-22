const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/monday/health";

function backendResponse(ok: boolean, data: any, status = ok ? 200 : 401): any {
  return { ok, status, json: async () => data };
}

describe("pages/api/integrations/monday/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (method: any = "GET", query: any = {}) => {
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 for non-GET methods", async () => {
    const res = await invoke("POST", { access_token: "tok" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when no access token is provided", async () => {
    const res = await invoke("GET", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Access token required",
      details: "Please provide Monday.com access token",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("forwards the health check with the bearer token and returns the backend data", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(true, { status: "healthy", boards: 3 }),
    );
    const res = await invoke("GET", { access_token: "monday-tok" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ status: "healthy", boards: 3 });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/monday/status?user_id=test_user");
    expect(init.method).toBe("GET");
    expect(init.headers).toEqual({
      Authorization: "Bearer monday-tok",
      "Content-Type": "application/json",
    });
  });

  it("passes through the backend failure with its detail", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(false, { detail: "invalid token" }, 401),
    );
    const res = await invoke("GET", { access_token: "bad" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      error: "Monday.com health check failed",
      details: "invalid token",
    });
  });

  it("uses a generic detail when the backend error has none", async () => {
    mockFetch.mockResolvedValue(backendResponse(false, {}, 503));
    const res = await invoke("GET", { access_token: "tok" });
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "Monday.com health check failed",
      details: "Unknown error",
    });
  });

  it("returns 500 with the error message when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("GET", { access_token: "tok" });
    expect(res._getStatusCode()).toBe(500);
    const body = res._getJSONData();
    expect(body.error).toBe("Monday.com service unavailable");
    expect(body.details).toBe("ECONNREFUSED");
    expect(body.timestamp).toEqual(expect.any(String));
    expect(console.error).toHaveBeenCalledWith(
      "Monday.com health check error:",
      expect.any(Error),
    );
  });

  it("returns 500 with a generic detail when a non-Error is thrown", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke("GET", { access_token: "tok" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().details).toBe("Unknown error");
  });
});
