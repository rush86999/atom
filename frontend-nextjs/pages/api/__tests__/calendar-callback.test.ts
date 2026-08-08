const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

const mockExchangeCodeForTokens = jest.fn();
jest.mock("@/lib/api-backend-helper", () => ({
  exchangeCodeForTokens: mockExchangeCodeForTokens,
}));

const mockExecuteGraphQLMutation = jest.fn();
jest.mock("@/lib/graphqlClient", () => ({
  executeGraphQLMutation: mockExecuteGraphQLMutation,
  executeGraphQLQuery: jest.fn(),
}));

const mockConstants = {
  postgraphileGraphUrl: "http://localhost:3000/api/graphql",
  postgraphileAdminSecret: "admin-secret",
};
jest.mock("@/lib/constants", () => mockConstants);

jest.mock("@/lib/logger", () => ({
  __esModule: true,
  default: {
    info: jest.fn(),
    error: jest.fn(),
    warn: jest.fn(),
    debug: jest.fn(),
  },
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/atom/auth/calendar/callback";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

const validTokens = {
  access_token: "at-1",
  refresh_token: "rt-1",
  expiry_date: Date.now() + 60 * 60 * 1000,
  scope: "calendar",
  token_type: "Bearer",
};

describe("pages/api/atom/auth/calendar/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    mockConstants.postgraphileGraphUrl = "http://localhost:3000/api/graphql";
    mockConstants.postgraphileAdminSecret = "admin-secret";
  });

  const invoke = async (url: string, session: any = mockSession) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({
      method: "GET",
      url,
      headers: { host: "localhost:3000" },
    }) as any;
    await handler(req, res);
    return res;
  };

  it("redirects to login when unauthenticated", async () => {
    const res = await invoke("/api/atom/auth/calendar/callback?code=x&state=user-1", null);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain(
      "/User/Login/UserLogin?error=session_expired_oauth_callback",
    );
  });

  it("redirects with the provider error when Google reports an error", async () => {
    const res = await invoke(
      "/api/atom/auth/calendar/callback?error=access_denied&state=user-1",
    );
    expect(res._getStatusCode()).toBe(302);
    const url = res._getRedirectUrl();
    expect(url).toContain("calendar_auth_error=access_denied");
    expect(url).toContain("atom_agent=true");
  });

  it("rejects a state mismatch as a CSRF attempt", async () => {
    const res = await invoke(
      "/api/atom/auth/calendar/callback?code=x&state=attacker-id",
    );
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("calendar_auth_error=invalid_state");
  });

  it("redirects when no authorization code is present", async () => {
    const res = await invoke("/api/atom/auth/calendar/callback?state=user-1");
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("calendar_auth_error=no_code_received");
  });

  it("redirects when the token exchange fails", async () => {
    mockExchangeCodeForTokens.mockResolvedValue(null);
    const res = await invoke(
      "/api/atom/auth/calendar/callback?code=bad&state=user-1",
    );
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain(
      "calendar_auth_error=token_exchange_failed",
    );
  });

  it("redirects with config error when GraphQL is not configured", async () => {
    mockExchangeCodeForTokens.mockResolvedValue(validTokens);
    mockConstants.postgraphileGraphUrl = "";
    const res = await invoke(
      "/api/atom/auth/calendar/callback?code=c1&state=user-1",
    );
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain(
      encodeURIComponent("GraphQL client is not configured."),
    );
  });

  it("redirects when saving tokens affects zero rows", async () => {
    mockExchangeCodeForTokens.mockResolvedValue(validTokens);
    mockExecuteGraphQLMutation.mockResolvedValue({
      insert_user_tokens: { affected_rows: 0 },
    });
    const res = await invoke(
      "/api/atom/auth/calendar/callback?code=c2&state=user-1",
    );
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain(
      encodeURIComponent("Token save did not affect any rows."),
    );
  });

  it("redirects with success after tokens are saved", async () => {
    mockExchangeCodeForTokens.mockResolvedValue(validTokens);
    mockExecuteGraphQLMutation.mockResolvedValue({
      insert_user_tokens: { affected_rows: 1 },
    });
    const res = await invoke(
      "/api/atom/auth/calendar/callback?code=c3&state=user-1",
    );
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("calendar_auth_success=true");
    const mutationCall = mockExecuteGraphQLMutation.mock.calls[0];
    expect(mutationCall[0]).toContain("UpsertUserToken");
    expect(mutationCall[1].objects[0]).toMatchObject({
      user_id: "user-1",
      service_name: "google_calendar",
      access_token: "at-1",
      refresh_token: "rt-1",
    });
  });

  it("redirects with generic error when the handler throws", async () => {
    mockExchangeCodeForTokens.mockRejectedValue(new Error("google outage"));
    const res = await invoke(
      "/api/atom/auth/calendar/callback?code=c4&state=user-1",
    );
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain(
      encodeURIComponent("callback_processing_failed"),
    );
  });
});
