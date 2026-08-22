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

describe("pages/api/auth/forgot-password", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    mockApiState.useBackendApi = false;
    process.env.NEXTAUTH_URL = "http://localhost:3000";
    process.env.NODE_ENV = "test";
    delete process.env.NEXT_PUBLIC_API_URL;
    mockSendEmail.mockResolvedValue(true);
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("SELECT id FROM users")) {
        return { rows: [] };
      }
      return { rows: [] };
    });
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_URL;
    process.env.NODE_ENV = "test";
  });

  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("returns 400 when email is missing", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Email is required" });
  });

  it("proxies to the backend API when the feature flag is enabled", async () => {
    mockApiState.useBackendApi = true;
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: "backend handled it" }),
    });
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: "backend handled it" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/forgot-password",
      expect.objectContaining({ method: "POST" }),
    );
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("falls back to the direct DB path when the backend replies non-OK", async () => {
    mockApiState.useBackendApi = true;
    mockFetch.mockResolvedValue({ ok: false, status: 500 });
    const res = await invoke("POST", { email: "missing@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message:
        "If an account exists with that email, a password reset link has been sent.",
    });
    expect(mockQuery).toHaveBeenCalled();
  });

  it("falls back to the direct DB path when the backend request throws", async () => {
    mockApiState.useBackendApi = true;
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("SELECT id FROM users")) {
        return { rows: [{ id: "user-1" }] };
      }
      return { rows: [] };
    });
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(console.error).toHaveBeenCalledWith(
      "Backend API error, falling back to direct DB:",
      "ECONNREFUSED",
    );
  });

  it("returns the generic success message for unknown emails", async () => {
    const res = await invoke("POST", { email: "nobody@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message:
        "If an account exists with that email, a password reset link has been sent.",
    });
    expect(mockSendEmail).not.toHaveBeenCalled();
  });

  it("stores a reset token and emails a reset link for a known user", async () => {
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("SELECT id FROM users")) {
        return { rows: [{ id: "user-1" }] };
      }
      return { rows: [] };
    });
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message:
        "If an account exists with that email, a password reset link has been sent.",
    });

    const insertCall = mockQuery.mock.calls.find(([text]: string[]) =>
      text.includes("INSERT INTO password_reset_tokens"),
    );
    expect(insertCall).toBeDefined();
    expect(insertCall[1][0]).toBe("user-1");
    expect(insertCall[1][1]).toMatch(/^[a-f0-9]{64}$/);
    expect(mockSendEmail).toHaveBeenCalledWith(
      expect.objectContaining({
        to: "u@example.com",
        subject: "Reset your Atom Platform password",
      }),
    );
    const emailHtml = mockSendEmail.mock.calls[0][0].html as string;
    expect(emailHtml).toContain("http://localhost:3000/auth/reset-password?token=");
    // Security: the DB must store the SHA-256 hash, never the raw emailed token
    const emailedToken = emailHtml.match(/token=([a-f0-9]+)/)?.[1] ?? "";
    expect(emailedToken).toMatch(/^[a-f0-9]{64}$/);
    expect(insertCall[1][1]).not.toBe(emailedToken);
  });

  it("includes the resetLink in development mode", async () => {
    process.env.NODE_ENV = "development";
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("SELECT id FROM users")) {
        return { rows: [{ id: "user-1" }] };
      }
      return { rows: [] };
    });
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().resetLink).toMatch(/^\/auth\/reset-password\?token=/);
  });

  it("still returns 200 when sending the email fails", async () => {
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("SELECT id FROM users")) {
        return { rows: [{ id: "user-1" }] };
      }
      return { rows: [] };
    });
    mockSendEmail.mockRejectedValue(new Error("SMTP down"));
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message:
        "If an account exists with that email, a password reset link has been sent.",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Failed to send password reset email:",
      expect.any(Error),
    );
  });

  it("returns 500 when the database query fails", async () => {
    mockQuery.mockRejectedValue(new Error("db down"));
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal server error" });
    expect(console.error).toHaveBeenCalled();
  });
});
