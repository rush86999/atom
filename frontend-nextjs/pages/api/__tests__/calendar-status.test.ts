const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

const mockExecuteGraphQLQuery = jest.fn();
jest.mock("@/lib/graphqlClient", () => ({
  executeGraphQLQuery: mockExecuteGraphQLQuery,
  executeGraphQLMutation: jest.fn(),
}));

const mockConstants = {
  postgraphileGraphUrl: "http://localhost:3000/api/graphql",
  postgraphileAdminSecret: "admin-secret",
  ATOM_GOOGLE_CALENDAR_CLIENT_ID: "g-client-id",
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: "g-client-secret",
};
jest.mock("@/lib/constants", () => mockConstants);

const mockGoogleApi = {
  oauth2Client: { setCredentials: jest.fn() },
  calendarListGet: jest.fn(),
};
const mockOAuth2 = jest.fn();
const mockCalendar = jest.fn();
jest.mock("googleapis", () => ({
  google: {
    auth: { OAuth2: mockOAuth2 },
    calendar: mockCalendar,
  },
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/atom/auth/calendar/status";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/atom/auth/calendar/status", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    mockConstants.postgraphileGraphUrl = "http://localhost:3000/api/graphql";
    mockConstants.postgraphileAdminSecret = "admin-secret";
    mockConstants.ATOM_GOOGLE_CALENDAR_CLIENT_ID = "g-client-id";
    mockConstants.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET = "g-client-secret";
    mockGoogleApi.calendarListGet.mockResolvedValue({ data: {} });
    mockOAuth2.mockImplementation(() => mockGoogleApi.oauth2Client);
    mockCalendar.mockReturnValue({
      calendarList: { get: mockGoogleApi.calendarListGet },
    });
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
      isConnected: false,
      error: "User not authenticated.",
    });
  });

  it("returns config_error when GraphQL is not configured", async () => {
    mockConstants.postgraphileGraphUrl = "";
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      isConnected: false,
      error: "config_error",
    });
  });

  it("reports not connected when no token rows exist", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({ user_tokens: [] });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ isConnected: false });
  });

  it("reports not connected when the token row has no access token", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({ user_tokens: [{ access_token: null }] });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ isConnected: false });
  });

  it("reports token_expired_no_refresh for an expired token without a refresh token", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ access_token: "at", refresh_token: null, expiry_date: "2000-01-01T00:00:00Z" }],
    });
    const res = await invoke();
    expect(res._getJSONData()).toEqual({
      isConnected: false,
      error: "token_expired_no_refresh",
    });
  });

  it("treats an expired token with a refresh token as connected when API test is unavailable", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ access_token: "at", refresh_token: "rt", expiry_date: "2000-01-01T00:00:00Z" }],
    });
    mockConstants.ATOM_GOOGLE_CALENDAR_CLIENT_ID = "";
    const res = await invoke();
    expect(res._getJSONData()).toEqual({ isConnected: true });
  });

  it("reports connected when the Google API test call succeeds", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ access_token: "at", refresh_token: "rt", expiry_date: "2099-01-01T00:00:00Z" }],
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ isConnected: true });
    expect(mockGoogleApi.oauth2Client.setCredentials).toHaveBeenCalledWith({
      access_token: "at",
      refresh_token: "rt",
    });
  });

  it("reports token_invalid_or_expired on invalid_grant from Google", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ access_token: "at", refresh_token: null, expiry_date: null }],
    });
    mockGoogleApi.calendarListGet.mockRejectedValue({
      response: { data: { error: "invalid_grant" } },
    });
    const res = await invoke();
    expect(res._getJSONData()).toEqual({
      isConnected: false,
      error: "token_invalid_or_expired",
    });
  });

  it("reports token_invalid_or_expired on 401 errors", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ access_token: "at", refresh_token: null, expiry_date: null }],
    });
    mockGoogleApi.calendarListGet.mockRejectedValue({ code: 401 });
    const res = await invoke();
    expect(res._getJSONData()).toEqual({
      isConnected: false,
      error: "token_invalid_or_expired",
    });
  });

  it("reports api_call_failed for other Google API errors", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_tokens: [{ access_token: "at", refresh_token: null, expiry_date: null }],
    });
    mockGoogleApi.calendarListGet.mockRejectedValue(new Error("rate limited"));
    const res = await invoke();
    expect(res._getJSONData()).toEqual({
      isConnected: false,
      error: "api_call_failed",
    });
  });

  it("reports status_check_exception when the GraphQL query throws", async () => {
    mockExecuteGraphQLQuery.mockRejectedValue(new Error("gql down"));
    const res = await invoke();
    expect(res._getJSONData()).toEqual({
      isConnected: false,
      error: "status_check_exception",
    });
  });
});
