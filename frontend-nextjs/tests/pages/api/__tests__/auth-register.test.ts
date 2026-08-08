const mockQuery = jest.fn();
jest.mock("@/lib/db", () => ({ query: mockQuery }));

const apiFlag = { USE_BACKEND_API: false, userManagementAPI: {} };
jest.mock("@/lib/api", () => apiFlag);

const mockBcryptHash = jest.fn().mockResolvedValue("hashed-password");
jest.mock("bcryptjs", () => ({
  hash: mockBcryptHash,
}));

const mockValidatePassword = jest.fn();
jest.mock("@/lib/password-validator", () => ({
  validatePassword: mockValidatePassword,
}));

const mockSendEmail = jest.fn();
const mockGenerateVerificationEmailHTML = jest.fn();
jest.mock("@/lib/email", () => ({
  sendEmail: mockSendEmail,
  generateVerificationEmailHTML: mockGenerateVerificationEmailHTML,
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/auth/register";

const mockFetch = jest.fn();

const strongPassword = "Str0ng!Passw0rd";

describe("pages/api/auth/register", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    apiFlag.USE_BACKEND_API = false;
    mockBcryptHash.mockResolvedValue("hashed-password");
    mockValidatePassword.mockReturnValue({ isValid: true, feedback: [] });
    mockGenerateVerificationEmailHTML.mockReturnValue("<html>verify</html>");
    mockSendEmail.mockResolvedValue(undefined);
    (global as any).fetch = mockFetch;
  });

  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 for non-POST methods", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData().error).toBe("Method not allowed");
  });

  it("returns 400 when email or password is missing", async () => {
    const res = await invoke("POST", { email: "a@b.com" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Email and password are required");
  });

  it("rejects weak passwords with feedback details", async () => {
    mockValidatePassword.mockReturnValue({
      isValid: false,
      feedback: ["Too short"],
    });
    const res = await invoke("POST", { email: "a@b.com", password: "weak" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Password does not meet security requirements",
      details: ["Too short"],
    });
  });

  it("passes through a successful backend registration", async () => {
    apiFlag.USE_BACKEND_API = true;
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: "registered via backend" }),
    });
    const res = await invoke("POST", {
      email: "a@b.com",
      password: strongPassword,
      name: "A",
    });
    expect(res._getStatusCode()).toBe(201);
    expect(res._getJSONData()).toEqual({ message: "registered via backend" });
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("passes through a 400 from the backend", async () => {
    apiFlag.USE_BACKEND_API = true;
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: "user exists" }),
    });
    const res = await invoke("POST", {
      email: "a@b.com",
      password: strongPassword,
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "user exists" });
  });

  it("falls back to direct DB when the backend fails", async () => {
    apiFlag.USE_BACKEND_API = true;
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      text: async () => "unavailable",
      json: async () => ({}),
    });
    mockQuery
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [{ id: "u1", email: "a@b.com", name: "A", created_at: "2026-01-01" }] })
      .mockResolvedValueOnce({ rows: [] });
    const res = await invoke("POST", {
      email: "a@b.com",
      password: strongPassword,
      name: "A",
    });
    expect(res._getStatusCode()).toBe(201);
  });

  it("falls back to direct DB when the backend fetch throws", async () => {
    apiFlag.USE_BACKEND_API = true;
    mockFetch.mockRejectedValue(new Error("connection refused"));
    mockQuery
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [{ id: "u1", email: "a@b.com", name: null, created_at: "2026-01-01" }] })
      .mockResolvedValueOnce({ rows: [] });
    const res = await invoke("POST", {
      email: "a@b.com",
      password: strongPassword,
    });
    expect(res._getStatusCode()).toBe(201);
  });

  it("returns 400 when the user already exists", async () => {
    mockQuery.mockResolvedValueOnce({ rows: [{ id: "existing" }] });
    const res = await invoke("POST", {
      email: "dup@b.com",
      password: strongPassword,
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("User already exists with this email");
  });

  it("creates the user, hashes the password, stores a verification token, and sends email", async () => {
    const userRow = { id: "u-77", email: "new@b.com", name: "New User", created_at: "2026-01-01T00:00:00Z" };
    mockQuery
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [userRow] })
      .mockResolvedValueOnce({ rows: [] });
    const res = await invoke("POST", {
      email: "new@b.com",
      password: strongPassword,
      name: "New User",
    });
    expect(res._getStatusCode()).toBe(201);
    const body = res._getJSONData();
    expect(body.message).toContain("User created successfully");
    expect(body.requiresVerification).toBe(true);
    expect(body.user).toEqual({
      id: "u-77",
      email: "new@b.com",
      name: "New User",
      createdAt: "2026-01-01T00:00:00Z",
    });
    const insertCall = mockQuery.mock.calls.find(
      (call: any) => (call[0] as string).includes("INSERT INTO users"),
    );
    expect(insertCall).toBeDefined();
    expect(insertCall[1][1]).toBe("hashed-password");
    const tokenCall = mockQuery.mock.calls.find(
      (call: any) => (call[0] as string).includes("email_verification_tokens"),
    );
    expect(tokenCall).toBeDefined();
    const code = tokenCall[1][1];
    expect(Number(code)).toBeGreaterThanOrEqual(100000);
    expect(Number(code)).toBeLessThanOrEqual(999999);
    expect(mockGenerateVerificationEmailHTML).toHaveBeenCalledWith(code, "New User");
    expect(mockSendEmail).toHaveBeenCalledWith({
      to: "new@b.com",
      subject: "Verify Your Email Address",
      html: "<html>verify</html>",
    });
  });

  it("still returns 201 when sending the verification email fails", async () => {
    mockSendEmail.mockRejectedValue(new Error("smtp down"));
    mockQuery
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [{ id: "u-1", email: "a@b.com", name: null, created_at: "2026-01-01" }] })
      .mockResolvedValueOnce({ rows: [] });
    const res = await invoke("POST", {
      email: "a@b.com",
      password: strongPassword,
    });
    expect(res._getStatusCode()).toBe(201);
  });

  it("returns 500 when the database throws", async () => {
    mockQuery.mockRejectedValue(new Error("db down"));
    const res = await invoke("POST", {
      email: "a@b.com",
      password: strongPassword,
    });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().error).toBe("Internal server error");
  });
});
