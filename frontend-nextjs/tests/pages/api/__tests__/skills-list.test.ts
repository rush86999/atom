const mockGetToken = jest.fn();
const mockGetSession = jest.fn();
jest.mock("next-auth/jwt", () => ({ getToken: mockGetToken }));
jest.mock("next-auth/react", () => ({ getSession: mockGetSession }));

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/skills/list";

const mockFetch = jest.fn();

const jsonResponse = (body: any, status = 200) => ({
  ok: status < 400,
  status,
  headers: {
    get: (name: string) =>
      name.toLowerCase() === "content-type" ? "application/json" : null,
  },
  json: async () => body,
  text: async () => JSON.stringify(body),
});

const htmlResponse = (status = 502) => ({
  ok: false,
  status,
  headers: {
    get: (name: string) => (name.toLowerCase() === "content-type" ? "text/html" : null),
  },
  json: async () => ({}),
  text: async () => "<html>Service Unavailable</html>",
});

describe("pages/api/skills/list", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
    jest.spyOn(console, "warn").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.BACKEND_API_URL;
    mockGetToken.mockResolvedValue(null);
    mockGetSession.mockResolvedValue(null);
    mockFetch.mockResolvedValue(
      jsonResponse({ success: true, data: { skills: [{ id: "s1" }], total: 1 } }),
    );
  });

  afterEach(() => {
    delete process.env.BACKEND_API_URL;
  });

  const invoke = async (method: RequestMethod = "GET", query: any = {}) => {
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ message: "Method Not Allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("proxies to the default backend URL and returns the skills payload", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: { skills: [{ id: "s1" }], total: 1 },
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/skills/list",
    );
    expect(res.getHeader("Cache-Control")).toBe(
      "s-maxage=60, stale-while-revalidate=300",
    );
  });

  it("prefers BACKEND_API_URL when set", async () => {
    process.env.BACKEND_API_URL = "http://backend:9000";
    await invoke();
    expect(mockFetch.mock.calls[0][0]).toBe("http://backend:9000/api/skills/list");
  });

  it("sends the Authorization header when the JWT contains an access token", async () => {
    mockGetToken.mockResolvedValue({ accessToken: "token-from-jwt" });
    await invoke();
    expect(mockFetch.mock.calls[0][1].headers["Authorization"]).toBe(
      "Bearer token-from-jwt",
    );
  });

  it("falls back to the session access token", async () => {
    mockGetSession.mockResolvedValue({ accessToken: "token-from-session" });
    await invoke();
    expect(mockFetch.mock.calls[0][1].headers["Authorization"]).toBe(
      "Bearer token-from-session",
    );
  });

  it("omits the Authorization header when no access token exists", async () => {
    await invoke();
    expect(mockFetch.mock.calls[0][1].headers).not.toHaveProperty("Authorization");
  });

  it("forwards query parameters to the backend", async () => {
    await invoke("GET", { status: "active", skill_type: "custom" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/skills/list?status=active&skill_type=custom",
    );
  });

  it("rejects non-JSON backend responses with the upstream status", async () => {
    mockFetch.mockResolvedValue(htmlResponse(502));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      error: "Invalid response from backend",
      details: "<html>Service Unavailable</html>",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns an empty list when the backend replies non-OK JSON", async () => {
    mockFetch.mockResolvedValue(jsonResponse({ error: "boom" }, 500));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: { skills: [], total: 0 },
      message: "No skills available",
    });
    expect(console.warn).toHaveBeenCalled();
  });

  it("returns an empty list when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: { skills: [], total: 0 },
      message: "Skills unavailable",
    });
    expect(console.warn).toHaveBeenCalled();
  });
});
