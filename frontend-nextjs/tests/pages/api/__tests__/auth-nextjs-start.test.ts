const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/auth/nextjs/start";

const backendSuccess = {
  authorization_url: "https://vercel.example/oauth/authorize",
  user_id: "user-1",
  csrf_token: "csrf-1",
};

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/auth/nextjs/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  const invoke = async (method = "POST", body?: any) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the user id is missing", async () => {
    const res = await invoke("POST", { scopes: ["read"] });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "User ID is required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("initiates the flow with default scopes and platform", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, backendSuccess));
    const res = await invoke("POST", { user_id: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, ...backendSuccess });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/nextjs/authorize",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          scopes: ["read", "projects", "deployments", "builds"],
          platform: "web",
        }),
      },
    );
  });

  it("forwards custom scopes/platform and honours the configured backend URL", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://python-backend:9999";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, backendSuccess));
    const res = await invoke("POST", {
      user_id: "user-2",
      scopes: ["read"],
      platform: "desktop",
    });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://python-backend:9999/api/auth/nextjs/authorize",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-2",
          scopes: ["read"],
          platform: "desktop",
        }),
      },
    );
  });

  it("mirrors the backend failure status and error message", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(false, 409, { error: "user already linked" }),
    );
    const res = await invoke("POST", { user_id: "user-3" });
    expect(res._getStatusCode()).toBe(409);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "user already linked",
    });
  });

  it("falls back to a generic error when the backend error body is empty", async () => {
    mockFetch.mockResolvedValue(jsonResponse(false, 500, {}));
    const res = await invoke("POST", { user_id: "user-4" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to initiate Next.js OAuth",
    });
  });

  it("returns 500 when the backend request itself fails", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const res = await invoke("POST", { user_id: "user-5" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
  });
});
