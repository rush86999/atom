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
import handler from "@/pages/api/zendesk/oauth/callback";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

function backendResponse(ok: boolean, data: any, status = ok ? 200 : 400): any {
  return { ok, status, json: async () => data };
}

describe("pages/api/zendesk/oauth/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetServerSession.mockResolvedValue(mockSession);
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:3000";
  });

  const invoke = async (query: any = {}, session: any = mockSession) => {
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
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("exchanges the code with the backend and redirects on success", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { connected: true }));
    const res = await invoke({ code: "zendesk-code" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations/zendesk?success=true");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/zendesk/auth/callback");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({
      code: "zendesk-code",
      user_id: "user-1",
      redirect_uri: "http://localhost:3000/api/zendesk/oauth/callback",
    });
  });

  it("returns 400 with the backend message when the exchange fails", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(false, { message: "invalid subdomain" }, 400),
    );
    const res = await invoke({ code: "bad" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Zendesk OAuth",
      message: "invalid subdomain",
    });
  });

  it("falls back to a generic message when the backend error has none", async () => {
    mockFetch.mockResolvedValue(backendResponse(false, {}, 500));
    const res = await invoke({ code: "bad" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Zendesk OAuth",
      message: "Unknown OAuth error",
    });
  });

  it("returns 500 when the backend request throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Zendesk OAuth flow",
      message: "ECONNREFUSED",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Zendesk OAuth callback error:",
      expect.any(Error),
    );
  });

  it("returns 500 with a generic message when a non-Error is thrown", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Zendesk OAuth flow",
      message: "Unknown error",
    });
  });
});
