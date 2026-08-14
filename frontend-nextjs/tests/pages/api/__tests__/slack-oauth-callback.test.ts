const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/slack/oauth/callback";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

function backendResponse(ok: boolean, data: any, status = ok ? 200 : 400): any {
  return { ok, status, json: async () => data };
}

describe("pages/api/slack/oauth/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetServerSession.mockResolvedValue(mockSession);
  });

  const invoke = async (
    method: any = "GET",
    query: any = {},
    session: any = mockSession,
  ) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST", { code: "c" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ message: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 401 when unauthenticated", async () => {
    const res = await invoke("GET", { code: "c" }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 401 when the session has no user", async () => {
    const res = await invoke("GET", { code: "c" }, { expires: "soon" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("redirects with the provider error when Slack reports one", async () => {
    const res = await invoke("GET", {
      error: "access_denied",
      error_description: "User denied consent",
    });
    expect(res._getStatusCode()).toBe(302);
    const url = res._getRedirectUrl();
    expect(url).toContain("status=error");
    expect(url).toContain("provider=slack");
    expect(url).toContain("error=access_denied");
    expect(url).toContain(encodeURIComponent("User denied consent"));
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("uses a default message when Slack reports an error without a description", async () => {
    const res = await invoke("GET", { error: "access_denied" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain(
      encodeURIComponent("Authorization failed"),
    );
  });

  it("redirects with missing_code when no authorization code is provided", async () => {
    const res = await invoke("GET", { state: "csrf" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("error=missing_code");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with missing_code when the code is not a string", async () => {
    const res = await invoke("GET", { code: ["a", "b"] });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("error=missing_code");
  });

  it("forwards the code to the backend and redirects with success", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { ok: true }));
    const res = await invoke("GET", { code: "oauth-code", state: "csrf-state" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("status=success");
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/v1/integrations/slack/oauth/callback");
    expect(init.method).toBe("POST");
    expect(init.headers["X-User-ID"]).toBe("user-1");
    expect(JSON.parse(init.body)).toEqual({
      code: "oauth-code",
      state: "csrf-state",
    });
  });

  it("sends a null state when none was provided", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { ok: true }));
    await invoke("GET", { code: "oauth-code" });
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body).state).toBeNull();
  });

  it("falls back to the session email for the X-User-ID header", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { ok: true }));
    await invoke("GET", { code: "c" }, { user: { email: "only-email@example.com" } });
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["X-User-ID"]).toBe("only-email@example.com");
  });

  it("omits the X-User-ID header when the session user has neither id nor email", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { ok: true }));
    await invoke("GET", { code: "c" }, { user: {} });
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["X-User-ID"]).toBeUndefined();
  });

  it("redirects with the backend error detail when the exchange fails", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(false, { error: "invalid_code", detail: "Code expired" }, 400),
    );
    const res = await invoke("GET", { code: "bad" });
    expect(res._getStatusCode()).toBe(302);
    const url = res._getRedirectUrl();
    expect(url).toContain("error=invalid_code");
    expect(url).toContain(encodeURIComponent("Code expired"));
  });

  it("falls back to the backend message when there is no detail", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(false, { error: "backend_error", message: "Backend exploded" }, 500),
    );
    const res = await invoke("GET", { code: "bad" });
    expect(res._getRedirectUrl()).toContain(encodeURIComponent("Backend exploded"));
  });

  it("falls back to a generic message when the backend error body is empty", async () => {
    mockFetch.mockResolvedValue(backendResponse(false, {}, 500));
    const res = await invoke("GET", { code: "bad" });
    const url = res._getRedirectUrl();
    expect(url).toContain("error=unknown");
    expect(url).toContain(encodeURIComponent("Failed to complete OAuth flow"));
  });

  it("redirects with server_error when the backend request throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("GET", { code: "c" });
    expect(res._getStatusCode()).toBe(302);
    const url = res._getRedirectUrl();
    expect(url).toContain("error=server_error");
    expect(url).toContain(encodeURIComponent("ECONNREFUSED"));
  });
});
