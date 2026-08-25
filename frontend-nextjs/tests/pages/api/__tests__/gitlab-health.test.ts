const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/gitlab/health";

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/gitlab/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  const invoke = async (method = "GET", body?: any) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects methods other than GET/POST with 405", async () => {
    const res = await invoke("DELETE");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("reports healthy for a successful GET check and reuses the backend timestamp", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(true, 200, { timestamp: "2026-08-14T00:00:00.000Z" }),
    );
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      status: "healthy",
      services: { gitlab: { status: "healthy", error: null } },
      timestamp: "2026-08-14T00:00:00.000Z",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/gitlab/health",
      { method: "GET", headers: {} },
    );
  });

  it("generates its own timestamp when the backend omits one", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(typeof body.timestamp).toBe("string");
    expect(body.timestamp).not.toBe("");
  });

  it("sends the X-User-ID header for POST requests carrying a user id", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    const res = await invoke("POST", { user_id: "user-9" });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/gitlab/health",
      { method: "GET", headers: { "X-User-ID": "user-9" } },
    );
  });

  it("omits the header for POST requests without a user id", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("POST", {});
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/gitlab/health",
      { method: "GET", headers: {} },
    );
  });

  it("honours NEXT_PUBLIC_API_BASE_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://python-backend:7777";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://python-backend:7777/api/gitlab/health",
      expect.anything(),
    );
  });

  it("reports unhealthy with the backend error when the check fails", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(false, 503, { error: "GitLab unreachable" }),
    );
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      status: "unhealthy",
      services: {
        gitlab: { status: "unhealthy", error: "GitLab unreachable" },
      },
    });
  });

  it("falls back to a generic error message when the backend error body is empty", async () => {
    mockFetch.mockResolvedValue(jsonResponse(false, 500, {}));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      status: "unhealthy",
      services: { gitlab: { status: "unhealthy", error: "Service unavailable" } },
    });
  });

  it("returns 500 unhealthy when the health fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("dns failure"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      status: "unhealthy",
      services: {
        gitlab: { status: "unhealthy", error: "Health check failed" },
      },
    });
  });
});
