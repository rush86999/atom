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
import handler from "@/pages/api/integrations/hubspot/callback";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/integrations/hubspot/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    mockGetServerSession.mockResolvedValue(mockSession);
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend.test";
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://fe.atom.test";
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
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

  it("exchanges the code with the backend and redirects on success", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations/hubspot?success=true");
    expect(mockFetch).toHaveBeenCalledWith("http://backend.test/api/hubspot/callback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: "c-1",
        user_id: "user-1",
        redirect_uri: "https://fe.atom.test/api/integrations/hubspot/callback",
      }),
    });
  });

  it("uses the default backend URL when the env var is unset", async () => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(302);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/hubspot/callback",
    );
  });

  it("returns 400 with the backend message when token exchange fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: async () => ({ message: "redirect_uri mismatch" }),
    });
    const res = await invoke({ code: "bad" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete HubSpot OAuth",
      message: "redirect_uri mismatch",
    });
  });

  it("defaults the error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue({ ok: false, json: async () => ({}) });
    const res = await invoke({ code: "bad" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete HubSpot OAuth",
      message: "Unknown OAuth error",
    });
  });

  it("returns 500 with the error message when fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("upstream refused"));
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete HubSpot OAuth flow",
      message: "upstream refused",
    });
    expect(console.error).toHaveBeenCalledWith(
      "HubSpot OAuth callback error:",
      expect.any(Error),
    );
  });

  it("returns 500 with Unknown error when a non-Error is thrown", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete HubSpot OAuth flow",
      message: "Unknown error",
    });
  });
});
