const mockQuery = jest.fn();
jest.mock("@/lib/db", () => ({ query: mockQuery }));

const apiFlag = { USE_BACKEND_API: false, userManagementAPI: {} };
jest.mock("@/lib/api", () => apiFlag);

const mockBcryptHash = jest.fn().mockResolvedValue("hashed-new-password");
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

const strongPassword = "N3w!SecurePass";

describe("pages/api/auth/reset-password", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    apiFlag.USE_BACKEND_API = false;
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
  });

  it("returns 400 when token or password is missing", async () => {
    const res = await invoke("POST", { token: "abc" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Token and password are required");
  });

  it("rejects weak passwords with feedback", async () => {
    mockValidatePassword.mockReturnValue({
      isValid: false,
      feedback: ["Needs a number"],
    });
    const res = await invoke("POST", { token: "abc", password: "weak" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Password does not meet security requirements",
      details: ["Needs a number"],
    });
  });

  it("passes through a successful backend reset", async () => {
    apiFlag.USE_BACKEND_API = true;
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: "reset via backend" }),
    });
    const res = await invoke("POST", { token: "t1", password: strongPassword });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: "reset via backend" });
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("passes through a 400 from the backend", async () => {
    apiFlag.USE_BACKEND_API = true;
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: "token expired" }),
    });
    const res = await invoke("POST", { token: "t1", password: strongPassword });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "token expired" });
  });

  it("falls back to direct DB when the backend fails or throws", async () => {
    apiFlag.USE_BACKEND_API = true;
    mockFetch.mockRejectedValue(new Error("boom"));
    mockQuery
      .mockResolvedValueOnce({
        rows: [
          {
            user_id: "u-1",
            expires_at: "2099-01-01T00:00:00Z",
            is_used: false,
          },
        ],
      })
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [] });
    const res = await invoke("POST", { token: "t1", password: strongPassword });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().message).toContain("reset successfully");
  });

  it("returns 400 for an unknown token", async () => {
    mockQuery.mockResolvedValueOnce({ rows: [] });
    const res = await invoke("POST", { token: "nope", password: strongPassword });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Invalid or expired reset token");
  });

  it("returns 400 for an expired token", async () => {
    mockQuery.mockResolvedValueOnce({
      rows: [{ user_id: "u-1", expires_at: "2020-01-01T00:00:00Z", is_used: false }],
    });
    const res = await invoke("POST", { token: "old", password: strongPassword });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Reset token has expired");
  });

  it("returns 400 for an already-used token", async () => {
    mockQuery.mockResolvedValueOnce({
      rows: [{ user_id: "u-1", expires_at: "2099-01-01T00:00:00Z", is_used: true }],
    });
    const res = await invoke("POST", { token: "used", password: strongPassword });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Reset token has already been used");
  });

  it("updates the password and marks the token used on success", async () => {
    mockQuery
      .mockResolvedValueOnce({
        rows: [
          { user_id: "u-1", expires_at: "2099-01-01T00:00:00Z", is_used: false },
        ],
      })
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [] });
    const res = await invoke("POST", { token: "t-valid", password: strongPassword });
    expect(res._getStatusCode()).toBe(200);
    expect(mockQuery.mock.calls[1][0]).toContain("UPDATE users SET password_hash");
    expect(mockQuery.mock.calls[1][1]).toEqual(["hashed-new-password", "u-1"]);
    expect(mockQuery.mock.calls[2][0]).toContain(
      "UPDATE password_reset_tokens SET is_used",
    );
  });

  it("returns 500 when the database throws", async () => {
    mockQuery.mockRejectedValue(new Error("db down"));
    const res = await invoke("POST", { token: "t1", password: strongPassword });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().error).toBe("Internal server error");
  });
});
