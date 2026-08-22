const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

jest.mock("@/pages/api/auth/[...nextauth]", () => ({
  authOptions: { providers: [] },
}));

const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/dropbox/callback";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/integrations/dropbox/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    mockGetServerSession.mockResolvedValue(mockSession);
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend.test";
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (
    query: any = { code: "c-1", state: "st-1" },
    session: any = mockSession,
  ) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method: "GET", query }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 401 when unauthenticated", async () => {
    const res = await invoke({ code: "c" }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 401 when the session has no user", async () => {
    const res = await invoke({ code: "c" }, { expires: "soon" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("forwards the code and state to the backend and redirects on success", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations/dropbox?success=true");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://backend.test/api/dropbox/callback?code=c-1&state=st-1",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("sends an empty state when none is present", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke({ code: "c-2" });
    expect(res._getRedirectUrl()).toBe("/integrations/dropbox?success=true");
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend.test/api/dropbox/callback?code=c-2&state=",
    );
  });

  it("uses the default backend URL when the env var is unset", async () => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(302);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/dropbox/callback?code=c&state=",
    );
  });

  it("returns 400 with the backend message when token exchange fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: async () => ({ message: "invalid_grant" }),
    });
    const res = await invoke({ code: "bad" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Dropbox OAuth",
      message: "invalid_grant",
    });
  });

  it("defaults the error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue({ ok: false, json: async () => ({}) });
    const res = await invoke({ code: "bad" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Dropbox OAuth",
      message: "Unknown OAuth error",
    });
  });

  it("returns 500 with the error message when fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("gateway timeout"));
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Dropbox OAuth flow",
      message: "gateway timeout",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Dropbox OAuth callback error:",
      expect.any(Error),
    );
  });

  it("returns 500 with Unknown error when a non-Error is thrown", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Dropbox OAuth flow",
      message: "Unknown error",
    });
  });
});
