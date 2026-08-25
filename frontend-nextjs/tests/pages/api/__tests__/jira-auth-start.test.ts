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
import handler from "@/pages/api/integrations/jira/auth/start";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/integrations/jira/auth/start", () => {
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

  const invoke = async (session: any = mockSession) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 401 when unauthenticated", async () => {
    const res = await invoke(null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 401 when the session has no user", async () => {
    const res = await invoke({ expires: "soon" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("requests the authorization URL from the backend and redirects", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ authorization_url: "https://auth.atlassian.com/authorize?client_id=x" }),
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://auth.atlassian.com/authorize?client_id=x",
    );
    expect(mockFetch).toHaveBeenCalledWith("http://backend.test/api/auth/jira/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: "user-1",
        redirect_uri: "https://fe.atom.test/api/integrations/jira/auth/callback",
      }),
    });
  });

  it("uses the default backend URL when the env var is unset", async () => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ authorization_url: "https://jira.example/auth" }),
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(mockFetch.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/auth/jira/start");
  });

  it("returns 500 when the backend response has no authorization URL", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to get Jira authorization URL",
      message: "No authorization URL returned from backend",
    });
  });

  it("returns 500 when the backend rejects the start request", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 503 });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Backend Jira service error",
      message: "Failed to contact Jira authentication service",
    });
  });

  it("returns 500 with the error message when fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("socket hang up"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to start Jira OAuth flow",
      message: "socket hang up",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Jira OAuth start error:",
      expect.any(Error),
    );
  });

  it("returns 500 with Unknown error when a non-Error is thrown", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to start Jira OAuth flow",
      message: "Unknown error",
    });
  });
});
