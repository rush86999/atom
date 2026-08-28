const mockQuery = jest.fn();
jest.mock("@/lib/db", () => ({ query: mockQuery }));

const mockApiState = { useBackendApi: false };
const mockSendVerificationEmail = jest.fn();
jest.mock("@/lib/api", () => ({
  get USE_BACKEND_API() {
    return mockApiState.useBackendApi;
  },
  emailVerificationAPI: {
    verifyEmail: jest.fn(),
    sendVerificationEmail: mockSendVerificationEmail,
  },
}));

const mockSendEmail = jest.fn();
const mockGenerateVerificationEmailHTML = jest.fn(
  (code: string) => `<p>code: ${code}</p>`,
);
jest.mock("@/lib/email", () => ({
  sendEmail: mockSendEmail,
  generateVerificationEmailHTML: mockGenerateVerificationEmailHTML,
}));

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/auth/send-verification-email";

describe("pages/api/auth/send-verification-email", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockApiState.useBackendApi = false;
    mockSendEmail.mockResolvedValue(true);
    mockGenerateVerificationEmailHTML.mockImplementation(
      (code: string) => `<p>code: ${code}</p>`,
    );
    mockQuery.mockImplementation(async (text: string) => {
      if (text.includes("FROM users")) {
        return { rows: [{ id: "user-1", name: "Alice", email_verified: false }] };
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

  it("returns 400 when email is missing", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Email is required" });
  });

  it("uses the backend API when the feature flag is enabled", async () => {
    mockApiState.useBackendApi = true;
    mockSendVerificationEmail.mockResolvedValue({ success: true });
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message: "Verification email sent successfully",
      email: "u@example.com",
    });
    expect(mockSendVerificationEmail).toHaveBeenCalledWith("u@example.com");
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it("falls back to the DB path when the backend API fails", async () => {
    mockApiState.useBackendApi = true;
    mockSendVerificationEmail.mockRejectedValue({ message: "backend down" });
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(console.error).toHaveBeenCalledWith(
      "Backend API error, falling back to direct DB:",
      "backend down",
    );
    expect(mockQuery).toHaveBeenCalled();
  });

  it("returns 404 when the user does not exist", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const res = await invoke("POST", { email: "nobody@example.com" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "User not found" });
  });

  it("returns 400 when the email is already verified", async () => {
    mockQuery.mockResolvedValue({
      rows: [{ id: "user-1", name: "Alice", email_verified: true }],
    });
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Email already verified" });
  });

  it("returns 500 when sending the email fails", async () => {
    mockSendEmail.mockResolvedValue(false);
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to send verification email. Please try again later.",
    });
  });

  it("rotates the verification token and emails the code", async () => {
    const res = await invoke("POST", { email: "u@example.com" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message: "Verification email sent successfully",
      email: "u@example.com",
    });

    const executedSql = mockQuery.mock.calls.map(([text]: string[]) => text);
    expect(executedSql).toEqual(
      expect.arrayContaining([
        expect.stringContaining("DELETE FROM email_verification_tokens"),
        expect.stringContaining("INSERT INTO email_verification_tokens"),
      ]),
    );
    const insert = mockQuery.mock.calls.find(
      ([text]: string[]) => text.includes("INSERT INTO email_verification_tokens"),
    );
    expect(insert[1][0]).toBe("user-1");
    expect(insert[1][1]).toMatch(/^\d{6}$/);
    expect(mockGenerateVerificationEmailHTML).toHaveBeenCalledWith(
      insert[1][1],
      "Alice",
    );
    expect(mockSendEmail).toHaveBeenCalledWith(
      expect.objectContaining({
        to: "u@example.com",
        subject: "Verify Your Email Address",
        html: `<p>code: ${insert[1][1]}</p>`,
      }),
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
