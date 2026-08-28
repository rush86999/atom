const mockQuery = jest.fn();
jest.mock("@/lib/db", () => ({ query: mockQuery }));

const mockApiState = { useBackendApi: false };
const mockVerifyEmail = jest.fn();
jest.mock("@/lib/api", () => ({
  get USE_BACKEND_API() {
    return mockApiState.useBackendApi;
  },
  emailVerificationAPI: {
    verifyEmail: mockVerifyEmail,
    sendVerificationEmail: jest.fn(),
  },
}));

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/auth/verify-email";

const existingUser = { rows: [{ id: "user-1", email_verified: false }] };

describe("pages/api/auth/verify-email", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockApiState.useBackendApi = false;
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("FROM users")) {
        return { rows: [{ id: "user-1", email_verified: false }] };
      }
      if (text.includes("FROM email_verification_tokens")) {
        return {
          rows: [{ token: "123456", expires_at: "2099-01-01T00:00:00Z" }],
        };
      }
      return { rows: [] };
    });
  });

  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("returns 400 when email or code is missing", async () => {
    const missingEmail = await invoke("POST", { code: "123456" });
    expect(missingEmail._getStatusCode()).toBe(400);
    expect(missingEmail._getJSONData()).toEqual({
      error: "Email and verification code are required",
    });

    const missingCode = await invoke("POST", { email: "u@example.com" });
    expect(missingCode._getStatusCode()).toBe(400);
    expect(missingCode._getJSONData()).toEqual({
      error: "Email and verification code are required",
    });
  });

  it("uses the backend API when the feature flag is enabled", async () => {
    mockApiState.useBackendApi = true;
    mockVerifyEmail.mockResolvedValue({ success: true });
    const res = await invoke("POST", { email: "u@example.com", code: "123456" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message: "Email verified successfully! You can now sign in.",
    });
    expect(mockVerifyEmail).toHaveBeenCalledWith("u@example.com", "123456");
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("maps a backend 400 to a 400 with the backend detail", async () => {
    mockApiState.useBackendApi = true;
    mockVerifyEmail.mockRejectedValue({
      message: "bad request",
      response: { status: 400, data: { detail: "Code expired" } },
    });
    const res = await invoke("POST", { email: "u@example.com", code: "000000" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Code expired" });
  });

  it("maps a backend 400 without detail to the generic message", async () => {
    mockApiState.useBackendApi = true;
    mockVerifyEmail.mockRejectedValue({
      message: "bad request",
      response: { status: 400 },
    });
    const res = await invoke("POST", { email: "u@example.com", code: "000000" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Invalid or expired code" });
  });

  it("maps a backend 404 to a 404", async () => {
    mockApiState.useBackendApi = true;
    mockVerifyEmail.mockRejectedValue({
      message: "not found",
      response: { status: 404 },
    });
    const res = await invoke("POST", { email: "u@example.com", code: "123456" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "User not found" });
  });

  it("falls back to the DB path on other backend errors", async () => {
    mockApiState.useBackendApi = true;
    mockVerifyEmail.mockRejectedValue({
      message: "boom",
      response: { status: 500 },
    });
    const res = await invoke("POST", { email: "u@example.com", code: "123456" });
    expect(res._getStatusCode()).toBe(200);
    expect(console.error).toHaveBeenCalledWith(
      "Backend API error, falling back to direct DB:",
      "boom",
    );
    expect(mockQuery).toHaveBeenCalled();
  });

  it("returns 404 when the user does not exist", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const res = await invoke("POST", { email: "nobody@example.com", code: "123456" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "User not found" });
  });

  it("returns 400 when the email is already verified", async () => {
    mockQuery.mockResolvedValue({
      rows: [{ id: "user-1", email_verified: true }],
    });
    const res = await invoke("POST", { email: "u@example.com", code: "123456" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Email already verified" });
  });

  it("returns 400 for an invalid verification code", async () => {
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("FROM users")) {
        return { rows: [{ id: "user-1", email_verified: false }] };
      }
      return { rows: [] };
    });
    const res = await invoke("POST", { email: "u@example.com", code: "000000" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Invalid verification code" });
  });

  it("returns 400 for an expired verification code", async () => {
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("FROM users")) {
        return { rows: [{ id: "user-1", email_verified: false }] };
      }
      return {
        rows: [{ token: "123456", expires_at: "2000-01-01T00:00:00Z" }],
      };
    });
    const res = await invoke("POST", { email: "u@example.com", code: "123456" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Verification code has expired. Please request a new one.",
    });
  });

  it("verifies the email and deletes the used token on success", async () => {
    const res = await invoke("POST", { email: "u@example.com", code: " 123456 " });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message: "Email verified successfully! You can now sign in.",
    });
    const executedSql = mockQuery.mock.calls.map(([text]: string[]) => text);
    expect(executedSql).toEqual(
      expect.arrayContaining([
        expect.stringContaining("UPDATE users SET email_verified = true"),
        expect.stringContaining("DELETE FROM email_verification_tokens"),
      ]),
    );
    const tokenLookup = mockQuery.mock.calls.find(
      ([text]: string[]) => text.includes("FROM email_verification_tokens") && text.includes("SELECT"),
    );
    expect(tokenLookup[1]).toEqual(["user-1", "123456"]);
  });

  it("returns 500 when the database query fails", async () => {
    mockQuery.mockRejectedValue(new Error("db down"));
    const res = await invoke("POST", { email: "u@example.com", code: "123456" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal server error" });
    expect(console.error).toHaveBeenCalled();
  });
});
