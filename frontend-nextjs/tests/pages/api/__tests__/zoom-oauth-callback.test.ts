const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("@/pages/api/auth/[...nextauth]", () => ({
  authOptions: { providers: [] },
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/zoom/oauth/callback";

const mockFetch = jest.fn();

const mockSession = {
  user: { id: "user-1", email: "u@example.com" },
  backendToken: "backend-tok",
};

describe("pages/api/zoom/oauth/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetServerSession.mockResolvedValue(mockSession);
    (global as any).fetch = mockFetch;
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true }),
    });
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (
    body: any = {},
    opts: { method?: string; session?: any } = {},
  ) => {
    mockGetServerSession.mockResolvedValue(
      opts.session === undefined ? mockSession : opts.session,
    );
    const { req, res } = createMocks({ method: (opts.method ?? "POST") as any, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke({}, { method: "GET" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("returns 401 when there is no session", async () => {
    const res = await invoke(
      { code: "c", state: "s", verifier: "v" },
      { session: null },
    );
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 401 when the session has no email", async () => {
    const res = await invoke(
      { code: "c", state: "s", verifier: "v" },
      { session: { user: { id: "user-1" }, backendToken: "t" } },
    );
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 401 when the backend token is missing", async () => {
    const res = await invoke(
      { code: "c", state: "s", verifier: "v" },
      { session: { user: { id: "user-1", email: "u@example.com" } } },
    );
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      error: "Missing authentication token",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the OAuth provider reported an error", async () => {
    const res = await invoke({ error: "access_denied" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "OAuth authorization failed",
      message: "access_denied",
    });
    expect(console.error).toHaveBeenCalled();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the authorization code is missing", async () => {
    const res = await invoke({ state: "s", verifier: "v" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Missing authorization code",
      message: "Authorization code is required",
    });
  });

  it("returns 400 when the PKCE verifier is missing", async () => {
    const res = await invoke({ code: "c", state: "s" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Missing PKCE verifier",
      message: "PKCE verifier is required for Zoom OAuth",
    });
  });

  it("returns 400 when the state parameter is missing", async () => {
    const res = await invoke({ code: "c", verifier: "v" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Missing state parameter",
      message: "State parameter is required for CSRF protection",
    });
  });

  it("forwards the OAuth exchange to the Python backend and redirects", async () => {
    const res = await invoke({ code: "zoom-code", state: "st", verifier: "pkce" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations/zoom?success=true&connected=true",
    );
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/zoom/oauth/callback",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-User-Email": "u@example.com",
          "X-User-ID": "user-1",
          Authorization: "Bearer backend-tok",
        }),
        body: JSON.stringify({
          code: "zoom-code",
          state: "st",
          verifier: "pkce",
          user_email: "u@example.com",
          user_id: "user-1",
        }),
      }),
    );
  });

  it("prefers PYTHON_API_SERVICE_BASE_URL when set", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://zoom-backend:5058";
    await invoke({ code: "c", state: "s", verifier: "v" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://zoom-backend:5058/api/integrations/zoom/oauth/callback",
    );
  });

  it("returns 400 with details when the backend rejects the exchange", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ message: "invalid code" }),
    });
    const res = await invoke({ code: "bad", state: "s", verifier: "v" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Zoom OAuth",
      message: "invalid code",
      details: { message: "invalid code" },
    });
  });

  it("defaults the backend error message when none is provided", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    const res = await invoke({ code: "c", state: "s", verifier: "v" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe("Unknown OAuth error");
  });

  it("returns 500 when the backend request throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke({ code: "c", state: "s", verifier: "v" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal server error",
      message: "Failed to complete Zoom OAuth flow",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
