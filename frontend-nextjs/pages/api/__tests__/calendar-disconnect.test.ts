const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

const mockExecuteGraphQLQuery = jest.fn();
const mockExecuteGraphQLMutation = jest.fn();
jest.mock("@/lib/graphqlClient", () => ({
  executeGraphQLQuery: mockExecuteGraphQLQuery,
  executeGraphQLMutation: mockExecuteGraphQLMutation,
}));

const mockConstants = {
  postgraphileGraphUrl: "http://localhost:3000/api/graphql",
  postgraphileAdminSecret: "admin-secret",
  ATOM_GOOGLE_CALENDAR_CLIENT_ID: "g-client-id",
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: "g-client-secret",
};
jest.mock("@/lib/constants", () => mockConstants);

const mockGoogleApi = {
  oauth2Client: { setCredentials: jest.fn(), revokeToken: jest.fn() },
};
const mockOAuth2 = jest.fn();
jest.mock("googleapis", () => ({
  google: {
    auth: { OAuth2: mockOAuth2 },
    calendar: jest.fn(),
  },
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/atom/auth/calendar/disconnect";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/atom/auth/calendar/disconnect", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    mockConstants.postgraphileGraphUrl = "http://localhost:3000/api/graphql";
    mockConstants.postgraphileAdminSecret = "admin-secret";
    mockConstants.ATOM_GOOGLE_CALENDAR_CLIENT_ID = "g-client-id";
    mockConstants.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET = "g-client-secret";
    mockGoogleApi.oauth2Client.revokeToken.mockResolvedValue(undefined);
    mockOAuth2.mockImplementation(() => mockGoogleApi.oauth2Client);
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
    expect(res._getJSONData()).toEqual({
      success: false,
      message: "User not authenticated.",
    });
  });

  it("returns 500 when GraphQL is not configured", async () => {
    mockConstants.postgraphileGraphUrl = "";
    mockExecuteGraphQLQuery.mockResolvedValue({ user_tokens: [] });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().message).toContain("database");
  });

  it("deletes local tokens and redirects with success when no refresh token exists", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({ user_tokens: [] });
    mockExecuteGraphQLMutation.mockResolvedValue({
      delete_user_tokens: { affected_rows: 1 },
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("calendar_disconnect_success=true");
    expect(mockGoogleApi.oauth2Client.revokeToken).not.toHaveBeenCalled();
    expect(mockExecuteGraphQLMutation.mock.calls[0][0]).toContain(
      "DeleteUserTokens",
    );
  });

  it("revokes the refresh token with Google before deleting local tokens", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ refresh_token: "rt-google-1" }],
    });
    mockExecuteGraphQLMutation.mockResolvedValue({
      delete_user_tokens: { affected_rows: 1 },
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("calendar_disconnect_success=true");
    expect(mockGoogleApi.oauth2Client.revokeToken).toHaveBeenCalledWith(
      "rt-google-1",
    );
  });

  it("still disconnects when Google revocation fails", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ refresh_token: "rt-google-1" }],
    });
    mockGoogleApi.oauth2Client.revokeToken.mockRejectedValue(
      new Error("invalid_token"),
    );
    mockExecuteGraphQLMutation.mockResolvedValue({
      delete_user_tokens: { affected_rows: 1 },
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("calendar_disconnect_success=true");
  });

  it("treats zero affected rows as a successful disconnect", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({ user_tokens: [] });
    mockExecuteGraphQLMutation.mockResolvedValue({
      delete_user_tokens: { affected_rows: 0 },
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("calendar_disconnect_success=true");
  });

  it("returns 500 when the delete mutation returns an unexpected shape", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({ user_tokens: [] });
    mockExecuteGraphQLMutation.mockResolvedValue({
      delete_user_tokens: null,
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().success).toBe(false);
  });

  it("returns 500 when the delete mutation throws", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({ user_tokens: [] });
    mockExecuteGraphQLMutation.mockRejectedValue(new Error("db down"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().success).toBe(false);
  });

  it("returns 500 when OAuth client config is missing and revocation is needed", async () => {
    mockConstants.ATOM_GOOGLE_CALENDAR_CLIENT_ID = "";
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ refresh_token: "rt" }],
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().message).toContain("unexpected error");
  });
});
