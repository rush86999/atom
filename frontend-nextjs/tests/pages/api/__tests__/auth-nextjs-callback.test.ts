const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/auth/nextjs/callback";

const backendSuccess = {
  access_token: "at-1",
  refresh_token: "rt-1",
  expires_at: 1234567890,
  user: { id: "u1", email: "u@example.com" },
  projects: [{ id: "p1", name: "proj" }],
  team_id: "team-1",
};

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/auth/nextjs/callback", () => {
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

  it("returns 400 when the authorization code is missing", async () => {
    const res = await invoke("POST", { state: "s-1" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Authorization code is required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("exchanges the code with the backend and returns the session payload", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, backendSuccess));
    const res = await invoke("POST", { code: "c-1", state: "s-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, ...backendSuccess });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/nextjs/callback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: "c-1", state: "s-1", platform: "web" }),
      },
    );
  });

  it("forwards the requested platform and honours the configured backend URL", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://python-backend:9999";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, backendSuccess));
    const res = await invoke("POST", { code: "c-2", platform: "desktop" });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://python-backend:9999/api/auth/nextjs/callback",
      expect.objectContaining({
        body: JSON.stringify({
          code: "c-2",
          state: undefined,
          platform: "desktop",
        }),
      }),
    );
  });

  it("mirrors the backend failure status and error message", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(false, 400, { error: "invalid_grant" }),
    );
    const res = await invoke("POST", { code: "bad" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ ok: false, error: "invalid_grant" });
  });

  it("falls back to a generic error when the backend error body is empty", async () => {
    mockFetch.mockResolvedValue(jsonResponse(false, 502, {}));
    const res = await invoke("POST", { code: "c-3" });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to complete Next.js OAuth",
    });
  });

  it("returns 500 when the backend request itself fails", async () => {
    mockFetch.mockRejectedValue(new Error("backend unreachable"));
    const res = await invoke("POST", { code: "c-4" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
  });
});
