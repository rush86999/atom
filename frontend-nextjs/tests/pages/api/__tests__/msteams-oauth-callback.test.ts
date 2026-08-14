const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("@/pages/api/auth/[...nextauth]", () => ({
  authOptions: { providers: [] },
}));

const mockExecuteGraphQLMutation = jest.fn();
jest.mock("@/lib/graphqlClient", () => ({
  executeGraphQLMutation: mockExecuteGraphQLMutation,
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/msteams/oauth/callback";

const mockFetch = jest.fn();

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/msteams/oauth/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetServerSession.mockResolvedValue(mockSession);
    (global as any).fetch = mockFetch;
    process.env.MSTEAMS_CLIENT_ID = "ms-client-id";
    process.env.MSTEAMS_CLIENT_SECRET = "ms-client-secret";
    process.env.MSTEAMS_REDIRECT_URI = "http://localhost:3000/api/msteams/oauth/callback";
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: "ms-at",
        refresh_token: "ms-rt",
        expires_in: 3600,
      }),
    });
    mockExecuteGraphQLMutation.mockResolvedValue({});
  });

  afterEach(() => {
    delete process.env.MSTEAMS_CLIENT_ID;
    delete process.env.MSTEAMS_CLIENT_SECRET;
    delete process.env.MSTEAMS_REDIRECT_URI;
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

  it("returns 500 when the MS Teams env vars are not configured", async () => {
    delete process.env.MSTEAMS_CLIENT_ID;
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Microsoft Teams environment variables not configured.",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 500 when the redirect URI is missing", async () => {
    delete process.env.MSTEAMS_REDIRECT_URI;
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Microsoft Teams environment variables not configured.",
    });
  });

  it("exchanges the code, saves tokens, and redirects to settings", async () => {
    const res = await invoke({ code: "ms-code", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/Settings/UserViewSettings");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://login.microsoftonline.com/common/oauth2/v2.0/token",
      expect.objectContaining({ method: "POST" }),
    );
    const requestBody = mockFetch.mock.calls[0][1].body as URLSearchParams;
    expect(requestBody.get("code")).toBe("ms-code");
    expect(requestBody.get("client_id")).toBe("ms-client-id");
    expect(requestBody.get("grant_type")).toBe("authorization_code");

    expect(mockExecuteGraphQLMutation).toHaveBeenCalledWith(
      expect.stringContaining("SaveTokens"),
      {
        userId: "user-1",
        service: "msteams",
        accessToken: "ms-at",
        refreshToken: "ms-rt",
        expiresAt: expect.any(String),
      },
    );
  });

  it("still redirects when saving the tokens fails", async () => {
    mockExecuteGraphQLMutation.mockRejectedValue(new Error("gql down"));
    const res = await invoke({ code: "ms-code" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/Settings/UserViewSettings");
    expect(console.error).toHaveBeenCalledWith(
      "Failed to save tokens:",
      expect.any(Error),
    );
  });

  it("returns 500 with the provider error when the token endpoint rejects", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        error: "invalid_grant",
        error_description: "AADSTS9002313: invalid code",
      }),
    });
    const res = await invoke({ code: "bad-code" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Microsoft Teams OAuth error: AADSTS9002313: invalid code",
    });
  });

  it("returns 500 when the token request throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke({ code: "ms-code" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Failed to complete Microsoft Teams OAuth flow",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
