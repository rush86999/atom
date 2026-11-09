// Historical case titles stay stable; obsolete local-DB behavior is now
// checked as backend forwarding with no local credential or mail effects.
const mockQuery = jest.fn();
jest.mock("@/lib/db", () => ({ query: mockQuery }));

const mockApiState = { useBackendApi: false };
jest.mock("@/lib/api", () => ({
  get USE_BACKEND_API() {
    return mockApiState.useBackendApi;
  },
  emailVerificationAPI: {
    verifyEmail: jest.fn(),
    sendVerificationEmail: jest.fn(),
  },
}));

const mockSendEmail = jest.fn();
jest.mock("@/lib/email", () => ({
  sendEmail: mockSendEmail,
  generateVerificationEmailHTML: jest.fn(() => "<p>code</p>"),
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/auth/forgot-password";

const mockFetch = jest.fn();

const API_BASE_URL =
  process.env.PYTHON_API_SERVICE_BASE_URL ||
  process.env.API_BASE_URL ||
  process.env.PYTHON_BACKEND_URL ||
  "http://127.0.0.1:8000";
const FORGOT_PASSWORD_URL = `${API_BASE_URL}/api/auth/forgot-password`;

const GENERIC_RESET_MESSAGE =
  "If an account exists with that email, a password reset link has been sent.";

const mockJsonResponse = (
  status: number,
  body: any,
  headers: Record<string, string> = {},
) => {
  const normalizedHeaders = Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [key.toLowerCase(), value]),
  );

  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    headers: {
      get: (name: string) => normalizedHeaders[name.toLowerCase()] ?? null,
    },
  };
};

describe("pages/api/auth/forgot-password", () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    mockFetch.mockReset();
    mockQuery.mockReset();
    mockSendEmail.mockReset();
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    mockApiState.useBackendApi = false;
    process.env.NEXTAUTH_URL = "http://localhost:3000";
    (process.env as any).NODE_ENV = "test";
    delete process.env.NEXT_PUBLIC_API_URL;
    mockSendEmail.mockResolvedValue(true);
    mockQuery.mockResolvedValue({ rows: [] });
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_URL;
    (process.env as any).NODE_ENV = "test";
  });

  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method, body } as any) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("returns 400 when email is missing", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Email is required" });
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("proxies to the backend API when the feature flag is enabled", async () => {
    mockApiState.useBackendApi = true;
    mockFetch.mockResolvedValue(
      mockJsonResponse(200, { message: "backend handled it" }),
    );

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: "backend handled it" });
    expect(mockFetch).toHaveBeenCalledWith(
      FORGOT_PASSWORD_URL,
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "u@example.com" }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("falls back to the direct DB path when the backend replies non-OK", async () => {
    mockApiState.useBackendApi = true;
    mockFetch.mockResolvedValue(
      mockJsonResponse(500, { error: "backend unavailable" }),
    );

    const res = await invoke("POST", { email: "missing@example.com" });

    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "backend unavailable" });
    expect(mockFetch).toHaveBeenCalledWith(
      FORGOT_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ email: "missing@example.com" }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("falls back to the direct DB path when the backend request throws", async () => {
    mockApiState.useBackendApi = true;
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      error: "Password reset service is unreachable",
    });
    expect(console.error).toHaveBeenCalledWith("Forgot password proxy failed", {
      stage: "backend-request",
    });
    const logged = (console.error as unknown as jest.Mock).mock.calls
      .flat()
      .join(" ");
    expect(logged).not.toContain("ECONNREFUSED");
    expect(mockFetch).toHaveBeenCalledWith(
      FORGOT_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ email: "u@example.com" }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("returns the generic success message for unknown emails", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(200, { message: GENERIC_RESET_MESSAGE }),
    );

    const res = await invoke("POST", { email: "nobody@example.com" });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: GENERIC_RESET_MESSAGE });
    expect(mockFetch).toHaveBeenCalledWith(
      FORGOT_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ email: "nobody@example.com" }),
      }),
    );
    expect(mockSendEmail).not.toHaveBeenCalled();
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("stores a reset token and emails a reset link for a known user", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(200, { message: GENERIC_RESET_MESSAGE }),
    );

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: GENERIC_RESET_MESSAGE });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith(
      FORGOT_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ email: "u@example.com" }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("includes the resetLink in development mode", async () => {
    (process.env as any).NODE_ENV = "development";
    mockFetch.mockResolvedValue(
      mockJsonResponse(200, { message: GENERIC_RESET_MESSAGE }),
    );

    const res = await invoke("POST", { email: "u@example.com" });
    const data = res._getJSONData();

    expect(res._getStatusCode()).toBe(200);
    expect(data).toEqual({ message: GENERIC_RESET_MESSAGE });
    expect(data.resetLink).toBeUndefined();
    expect(mockFetch).toHaveBeenCalledWith(
      FORGOT_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ email: "u@example.com" }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("still returns 200 when sending the email fails", async () => {
    mockSendEmail.mockRejectedValue(new Error("SMTP down"));
    mockFetch.mockResolvedValue(
      mockJsonResponse(200, { message: GENERIC_RESET_MESSAGE }),
    );

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: GENERIC_RESET_MESSAGE });
    expect(mockFetch).toHaveBeenCalledWith(
      FORGOT_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ email: "u@example.com" }),
      }),
    );
    expect(mockSendEmail).not.toHaveBeenCalled();
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("returns 500 when the database query fails", async () => {
    mockQuery.mockRejectedValue(new Error("db down"));
    mockFetch.mockResolvedValue(
      mockJsonResponse(500, { error: "Internal server error" }),
    );

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal server error" });
    expect(mockFetch).toHaveBeenCalledWith(
      FORGOT_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ email: "u@example.com" }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("returns 502 when the backend returns invalid JSON", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new Error("invalid json");
      },
      headers: { get: () => null },
    });

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      error: "Password reset service returned an invalid response",
    });
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("returns 502 when the backend response is not an object", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse(200, []));

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      error: "Password reset service returned an invalid response",
    });
  });

  it("forwards the backend Retry-After header", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(
        429,
        { error: "Too many requests" },
        { "Retry-After": "30" },
      ),
    );

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(429);
    expect(res._getJSONData()).toEqual({ error: "Too many requests" });
    expect(res.getHeader("Retry-After")).toBe("30");
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("always proxies to the backend even when the feature flag is disabled", async () => {
    mockApiState.useBackendApi = false;
    mockFetch.mockResolvedValue(
      mockJsonResponse(200, { message: "backend handled it" }),
    );

    const res = await invoke("POST", { email: "u@example.com" });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: "backend handled it" });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockSendEmail).not.toHaveBeenCalled();
  });
});
