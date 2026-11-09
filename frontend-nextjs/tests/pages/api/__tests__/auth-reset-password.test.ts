// Historical case titles stay stable; obsolete local-DB behavior is now
// checked as backend forwarding with no local credential or mail effects.
const mockQuery = jest.fn();
jest.mock("@/lib/db", () => ({ query: mockQuery }));

const mockBcryptHash = jest.fn();
jest.mock("bcryptjs", () => ({
  hash: mockBcryptHash,
}));

const mockValidatePassword = jest.fn();
jest.mock("@/lib/password-validator", () => ({
  validatePassword: mockValidatePassword,
}));

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/auth/reset-password";

const mockFetch = jest.fn();

const API_BASE_URL = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.API_BASE_URL || process.env.PYTHON_BACKEND_URL || "http://127.0.0.1:8000";
const RESET_PASSWORD_URL = `${API_BASE_URL}/api/auth/reset-password`;

const strongPassword = "N3w!SecurePass";

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

describe("pages/api/auth/reset-password", () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    mockFetch.mockReset();
    mockQuery.mockReset();
    mockBcryptHash.mockReset();
    mockValidatePassword.mockReset();
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockBcryptHash.mockResolvedValue("hashed-new-password");
    mockValidatePassword.mockReturnValue({ isValid: true, feedback: [] });
    (global as any).fetch = mockFetch;
  });

  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 for non-POST methods", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData().error).toBe("Method not allowed");
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockBcryptHash).not.toHaveBeenCalled();
  });

  it("returns 400 when token or password is missing", async () => {
    const missingToken = await invoke("POST", { password: strongPassword });
    expect(missingToken._getStatusCode()).toBe(400);
    expect(missingToken._getJSONData().error).toBe(
      "Token and password are required",
    );

    const missingPassword = await invoke("POST", { token: "abc" });
    expect(missingPassword._getStatusCode()).toBe(400);
    expect(missingPassword._getJSONData().error).toBe(
      "Token and password are required",
    );

    const blankToken = await invoke("POST", {
      token: "   ",
      password: strongPassword,
    });
    expect(blankToken._getStatusCode()).toBe(400);
    expect(blankToken._getJSONData().error).toBe(
      "Token and password are required",
    );

    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("rejects weak passwords with feedback", async () => {
    const shortPassword = await invoke("POST", {
      token: "abc",
      password: "weak",
    });
    expect(shortPassword._getStatusCode()).toBe(400);
    expect(shortPassword._getJSONData()).toEqual({
      error: "Password must be at least 8 characters long",
    });

    const longPassword = await invoke("POST", {
      token: "abc",
      password: "a".repeat(129),
    });
    expect(longPassword._getStatusCode()).toBe(400);
    expect(longPassword._getJSONData()).toEqual({
      error: "Password must be at most 128 characters",
    });

    const multibytePassword = await invoke("POST", {
      token: "abc",
      password: "\u00e9".repeat(37),
    });
    expect(multibytePassword._getStatusCode()).toBe(400);
    expect(multibytePassword._getJSONData()).toEqual({
      error: "Password must be at most 72 bytes when UTF-8 encoded",
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockValidatePassword).not.toHaveBeenCalled();
  });

  it("passes through a successful backend reset", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(200, { message: "reset via backend" }),
    );

    const res = await invoke("POST", { token: "t1", password: strongPassword });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: "reset via backend" });
    expect(mockFetch).toHaveBeenCalledWith(
      RESET_PASSWORD_URL,
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: "t1", password: strongPassword }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockBcryptHash).not.toHaveBeenCalled();
    expect(mockValidatePassword).not.toHaveBeenCalled();
  });

  it("passes through a 400 from the backend", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(400, { error: "token expired" }),
    );

    const res = await invoke("POST", { token: "t1", password: strongPassword });

    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "token expired" });
    expect(mockFetch).toHaveBeenCalledWith(
      RESET_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ token: "t1", password: strongPassword }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("falls back to direct DB when the backend fails or throws", async () => {
    mockFetch.mockRejectedValueOnce(new Error("boom"));

    const thrown = await invoke("POST", {
      token: "t1",
      password: strongPassword,
    });

    expect(thrown._getStatusCode()).toBe(502);
    expect(thrown._getJSONData()).toEqual({
      error: "Password reset service is unreachable",
    });
    expect(console.error).toHaveBeenCalledWith("Reset password proxy failed", {
      stage: "backend-request",
    });
    const logged = (console.error as unknown as jest.Mock).mock.calls
      .flat()
      .join(" ");
    expect(logged).not.toContain("boom");
    expect(mockFetch).toHaveBeenCalledWith(
      RESET_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ token: "t1", password: strongPassword }),
      }),
    );

    mockFetch.mockResolvedValueOnce(
      mockJsonResponse(503, { error: "service unavailable" }),
    );
    const failed = await invoke("POST", {
      token: "t1",
      password: strongPassword,
    });

    expect(failed._getStatusCode()).toBe(503);
    expect(failed._getJSONData()).toEqual({ error: "service unavailable" });
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockBcryptHash).not.toHaveBeenCalled();
  });

  it("returns 400 for an unknown token", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(400, { error: "Invalid or expired reset token" }),
    );

    const res = await invoke("POST", {
      token: "nope",
      password: strongPassword,
    });

    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Invalid or expired reset token");
    expect(mockFetch).toHaveBeenCalledWith(
      RESET_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ token: "nope", password: strongPassword }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("returns 400 for an expired token", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(400, { error: "Reset token has expired" }),
    );

    const res = await invoke("POST", {
      token: "old",
      password: strongPassword,
    });

    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Reset token has expired");
    expect(mockFetch).toHaveBeenCalledWith(
      RESET_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ token: "old", password: strongPassword }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("returns 400 for an already-used token", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(400, { error: "Reset token has already been used" }),
    );

    const res = await invoke("POST", {
      token: "used",
      password: strongPassword,
    });

    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Reset token has already been used");
    expect(mockFetch).toHaveBeenCalledWith(
      RESET_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ token: "used", password: strongPassword }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("updates the password and marks the token used on success", async () => {
    mockFetch.mockResolvedValue(
      mockJsonResponse(200, { message: "Password reset successfully" }),
    );

    const res = await invoke("POST", {
      token: "t-valid",
      password: strongPassword,
    });

    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message: "Password reset successfully",
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith(
      RESET_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({
          token: "t-valid",
          password: strongPassword,
        }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockBcryptHash).not.toHaveBeenCalled();
  });

  it("returns 500 when the database throws", async () => {
    mockQuery.mockRejectedValue(new Error("db down"));
    mockFetch.mockResolvedValue(
      mockJsonResponse(500, { error: "Internal server error" }),
    );

    const res = await invoke("POST", { token: "t1", password: strongPassword });

    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().error).toBe("Internal server error");
    expect(mockFetch).toHaveBeenCalledWith(
      RESET_PASSWORD_URL,
      expect.objectContaining({
        body: JSON.stringify({ token: "t1", password: strongPassword }),
      }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
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

    const res = await invoke("POST", { token: "t1", password: strongPassword });

    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      error: "Password reset service returned an invalid response",
    });
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockBcryptHash).not.toHaveBeenCalled();
  });

  it("returns 502 when the backend response is not an object", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse(200, []));

    const res = await invoke("POST", { token: "t1", password: strongPassword });

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
        { "Retry-After": "120" },
      ),
    );

    const res = await invoke("POST", { token: "t1", password: strongPassword });

    expect(res._getStatusCode()).toBe(429);
    expect(res._getJSONData()).toEqual({ error: "Too many requests" });
    expect(res.getHeader("Retry-After")).toBe("120");
    expect(mockQuery).not.toHaveBeenCalled();
    expect(mockBcryptHash).not.toHaveBeenCalled();
  });
});
