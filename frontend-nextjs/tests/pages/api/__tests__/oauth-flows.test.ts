const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));

const mockGenerateGoogleAuthUrl = jest.fn();
jest.mock("@lib/api-backend-helper", () => ({
  generateGoogleAuthUrl: mockGenerateGoogleAuthUrl,
}));

const mockExecuteGraphQLQuery = jest.fn();
const mockExecuteGraphQLMutation = jest.fn();
jest.mock("@lib/graphqlClient", () => ({
  executeGraphQLQuery: mockExecuteGraphQLQuery,
  executeGraphQLMutation: mockExecuteGraphQLMutation,
}));

const mockCreateToken = jest.fn();
const mockOAuthClient = jest.fn();
jest.mock("intuit-oauth", () => ({ __esModule: true, default: mockOAuthClient }));

import { createMocks } from "node-mocks-http";
import calendarInitiate from "@/pages/api/atom/auth/calendar/initiate";
import getZapierUrl from "@/pages/api/atom/integrations/get-zapier-url";
import saveZapierUrl from "@/pages/api/atom/integrations/save-zapier-url";
import notionStart from "@/pages/api/notion/start";
import notionCallback from "@/pages/api/notion/callback";
import teamsStart from "@/pages/api/teams/start";
import teamsCallback from "@/pages/api/teams/callback";
import pocketStart from "@/pages/api/pocket/oauth/start";
import pocketCallback from "@/pages/api/pocket/oauth/callback";
import quickbooksCallback from "@/pages/api/quickbooks/oauth/callback";

const mockFetch = jest.fn();
const httpResponse = (ok: boolean, status: number, data: any, headers: Record<string, string> = {}): any => ({
  ok,
  status,
  json: async () => data,
  text: async () => (typeof data === "string" ? data : JSON.stringify(data)),
  headers: { get: (name: string) => headers[name] ?? null },
});

describe("pages/api/atom/auth/calendar/initiate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({ user: { id: "u1" } });
    mockGenerateGoogleAuthUrl.mockReturnValue("https://accounts.google.com/o/oauth2/auth?state=u1");
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("redirects to the generated Google auth URL", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await calendarInitiate(req, res);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("https://accounts.google.com/o/oauth2/auth?state=u1");
    expect(mockGenerateGoogleAuthUrl).toHaveBeenCalledWith("u1");
  });

  it("returns 401 when there is no session", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "GET" }) as any;
    await calendarInitiate(req, res);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Authentication required." });
  });

  it("returns 401 when the session has no user id", async () => {
    mockGetServerSession.mockResolvedValue({ user: {} });
    const { req, res } = createMocks({ method: "GET" }) as any;
    await calendarInitiate(req, res);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Authentication required." });
  });

  it("returns 500 when auth URL generation throws", async () => {
    mockGenerateGoogleAuthUrl.mockImplementation(() => {
      throw new Error("boom");
    });
    const { req, res } = createMocks({ method: "GET" }) as any;
    await calendarInitiate(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      statusCode: 500,
      message: "Failed to initiate Google authentication.",
    });
  });
});

describe("pages/api/atom/integrations/get-zapier-url", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({ user: { id: "u1" } });
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("returns 401 without a session", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "GET" }) as any;
    await getZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(401);
  });

  it("returns the stored zapier url", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({
      user_settings: [{ value: "https://hooks.zapier.com/abc" }],
    });
    const { req, res } = createMocks({ method: "GET" }) as any;
    await getZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ url: "https://hooks.zapier.com/abc" });
  });

  it("returns null url when no setting exists", async () => {
    mockExecuteGraphQLQuery.mockResolvedValue({ user_settings: [] });
    const { req, res } = createMocks({ method: "GET" }) as any;
    await getZapierUrl(req, res);
    expect(res._getJSONData()).toEqual({ url: null });
  });

  it("returns 500 when the query fails", async () => {
    mockExecuteGraphQLQuery.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await getZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Failed to fetch Zapier URL" });
  });

  it("rejects non-GET with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await getZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getHeaders().allow).toEqual(["GET"]);
  });
});

describe("pages/api/atom/integrations/save-zapier-url", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({ user: { id: "u1" } });
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("returns 401 without a session", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "POST", body: { url: "u" } }) as any;
    await saveZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(401);
  });

  it("returns 400 when the url is missing", async () => {
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await saveZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ message: "URL is required" });
    expect(mockExecuteGraphQLMutation).not.toHaveBeenCalled();
  });

  it("saves the url via mutation", async () => {
    mockExecuteGraphQLMutation.mockResolvedValue({});
    const { req, res } = createMocks({ method: "POST", body: { url: "https://hooks.zapier.com/x" } }) as any;
    await saveZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: "Zapier URL saved successfully" });
    expect(mockExecuteGraphQLMutation).toHaveBeenCalledWith(
      expect.stringContaining("InsertUserSetting"),
      expect.objectContaining({ userId: "u1", key: "zapier_webhook_url", value: "https://hooks.zapier.com/x" }),
      "InsertUserSetting",
      "u1",
    );
  });

  it("returns 500 when the mutation fails", async () => {
    mockExecuteGraphQLMutation.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "POST", body: { url: "u" } }) as any;
    await saveZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Failed to save Zapier URL" });
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await saveZapierUrl(req, res);
    expect(res._getStatusCode()).toBe(405);
  });
});

describe("pages/api/notion/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-GET with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await notionStart(req, res);
    expect(res._getStatusCode()).toBe(405);
  });

  it("returns 400 when user_id is missing", async () => {
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await notionStart(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "user_id parameter is required" });
  });

  it("forwards the user_id and returns the auth payload", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { auth_url: "https://api.notion.com/v1/oauth/authorize?x=1", user_id: "u1", csrf_token: "t" }));
    const { req, res } = createMocks({ method: "GET", query: { user_id: "u1" } }) as any;
    await notionStart(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true, auth_url: "https://api.notion.com/v1/oauth/authorize?x=1", user_id: "u1", csrf_token: "t" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/notion/authorize?user_id=u1",
      { method: "GET", headers: { "Content-Type": "application/json" } },
    );
  });

  it("mirrors backend errors with a fallback message", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 502, {}));
    const { req, res } = createMocks({ method: "GET", query: { user_id: "u1" } }) as any;
    await notionStart(req, res);
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({ error: "Failed to start Notion OAuth" });
  });

  it("uses the backend error message when present", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 401, { error: "unauthorized" }));
    const { req, res } = createMocks({ method: "GET", query: { user_id: "u1" } }) as any;
    await notionStart(req, res);
    expect(res._getJSONData()).toEqual({ error: "unauthorized" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: { user_id: "u1" } }) as any;
    await notionStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal server error", message: "down" });
  });
});

describe("pages/api/notion/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await notionCallback(req, res);
    expect(res._getStatusCode()).toBe(405);
  });

  it("returns 400 when code is missing", async () => {
    const { req, res } = createMocks({ method: "POST", body: { state: "s" } }) as any;
    await notionCallback(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Authorization code is required" });
  });

  it("returns 400 when state is missing", async () => {
    const { req, res } = createMocks({ method: "POST", body: { code: "c" } }) as any;
    await notionCallback(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "State parameter is required" });
  });

  it("returns backend json data on success", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { connected: true }, { "content-type": "application/json" }));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await notionCallback(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true, connected: true });
  });

  it("returns redirect_url for 3xx responses", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 302, "redirecting", { location: "https://notion.so/connected" }));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await notionCallback(req, res);
    expect(res._getJSONData()).toEqual({
      success: true,
      redirect_url: "https://notion.so/connected",
      message: "Notion connected successfully",
    });
  });

  it("returns a generic success message for non-json non-redirect bodies", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, "ok"));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await notionCallback(req, res);
    expect(res._getJSONData()).toEqual({
      success: true,
      message: "Notion OAuth callback processed successfully",
    });
  });

  it("mirrors backend failure with details", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 400, "bad code"));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await notionCallback(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to process Notion OAuth callback",
      details: "bad code",
    });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await notionCallback(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal server error", message: "down" });
  });
});

describe("pages/api/teams/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-GET with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await teamsStart(req, res);
    expect(res._getStatusCode()).toBe(405);
  });

  it("returns 400 when user_id is missing", async () => {
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await teamsStart(req, res);
    expect(res._getStatusCode()).toBe(400);
  });

  it("forwards user_id and returns the auth payload", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { auth_url: "https://login.microsoftonline.com/authorize", user_id: "u1", csrf_token: "t" }));
    const { req, res } = createMocks({ method: "GET", query: { user_id: "u1" } }) as any;
    await teamsStart(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true, auth_url: "https://login.microsoftonline.com/authorize", user_id: "u1", csrf_token: "t" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/teams/authorize?user_id=u1",
      expect.anything(),
    );
  });

  it("mirrors backend error with fallback message", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 502, {}));
    const { req, res } = createMocks({ method: "GET", query: { user_id: "u1" } }) as any;
    await teamsStart(req, res);
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({ error: "Failed to start Teams OAuth" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: { user_id: "u1" } }) as any;
    await teamsStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal server error", message: "down" });
  });
});

describe("pages/api/teams/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await teamsCallback(req, res);
    expect(res._getStatusCode()).toBe(405);
  });

  it("returns 400 when code or state is missing", async () => {
    const { req, res } = createMocks({ method: "POST", body: { state: "s" } }) as any;
    await teamsCallback(req, res);
    expect(res._getStatusCode()).toBe(400);
    const { req: req2, res: res2 } = createMocks({ method: "POST", body: { code: "c" } }) as any;
    await teamsCallback(req2, res2);
    expect(res2._getStatusCode()).toBe(400);
  });

  it("returns backend json data on success", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { ok: true }, { "content-type": "application/json" }));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await teamsCallback(req, res);
    expect(res._getJSONData()).toEqual({ success: true, ok: true });
  });

  it("returns redirect_url for 3xx responses", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 302, "", { location: "https://teams.microsoft.com/ok" }));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await teamsCallback(req, res);
    expect(res._getJSONData()).toEqual({
      success: true,
      redirect_url: "https://teams.microsoft.com/ok",
      message: "Teams connected successfully",
    });
  });

  it("returns a generic success message for plain bodies", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, "ok"));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await teamsCallback(req, res);
    expect(res._getJSONData()).toEqual({
      success: true,
      message: "Teams OAuth callback processed successfully",
    });
  });

  it("mirrors backend failure with details", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 400, "bad"));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await teamsCallback(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to process Teams OAuth callback",
      details: "bad",
    });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "POST", body: { code: "c", state: "s" } }) as any;
    await teamsCallback(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Internal server error", message: "down" });
  });
});

describe("pages/api/pocket/oauth/start", () => {
  const oldEnv = { ...process.env };

  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    process.env = { ...oldEnv };
  });

  it("returns 500 when env vars are not configured", async () => {
    delete process.env.POCKET_CONSUMER_KEY;
    delete process.env.POCKET_REDIRECT_URI;
    const { req, res } = createMocks({ method: "GET" }) as any;
    await pocketStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Pocket environment variables not configured." });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects to the Pocket authorization URL", async () => {
    process.env.POCKET_CONSUMER_KEY = "key1";
    process.env.POCKET_REDIRECT_URI = "http://localhost:3000/cb";
    mockFetch.mockResolvedValue(httpResponse(true, 200, { code: "req-token" }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await pocketStart(req, res);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://getpocket.com/auth/authorize?request_token=req-token&redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fcb",
    );
    expect(mockFetch).toHaveBeenCalledWith(
      "https://getpocket.com/v3/oauth/request",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=UTF-8", "X-Accept": "application/json" },
        body: JSON.stringify({ consumer_key: "key1", redirect_uri: "http://localhost:3000/cb" }),
      },
    );
  });

  it("returns 500 when the token request fails", async () => {
    process.env.POCKET_CONSUMER_KEY = "key1";
    process.env.POCKET_REDIRECT_URI = "http://localhost:3000/cb";
    mockFetch.mockResolvedValue(httpResponse(false, 401, "denied"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await pocketStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Failed to start Pocket authentication" });
  });

  it("returns 500 when fetch rejects", async () => {
    process.env.POCKET_CONSUMER_KEY = "key1";
    process.env.POCKET_REDIRECT_URI = "http://localhost:3000/cb";
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await pocketStart(req, res);
    expect(res._getStatusCode()).toBe(500);
  });
});

describe("pages/api/pocket/oauth/callback", () => {
  const oldEnv = { ...process.env };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({ user: { id: "u1" } });
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    process.env = { ...oldEnv };
  });

  it("returns 401 without a session", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await pocketCallback(req, res);
    expect(res._getStatusCode()).toBe(401);
  });

  it("returns 500 when the consumer key is not configured", async () => {
    delete process.env.POCKET_CONSUMER_KEY;
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await pocketCallback(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Pocket consumer key not configured." });
  });

  it("exchanges the code, stores the token, and redirects", async () => {
    process.env.POCKET_CONSUMER_KEY = "key1";
    mockFetch.mockResolvedValue(httpResponse(true, 200, { access_token: "at1" }));
    mockExecuteGraphQLQuery.mockResolvedValue({});
    const { req, res } = createMocks({ method: "GET", query: { code: "c1" } }) as any;
    await pocketCallback(req, res);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/Settings/UserViewSettings");
    expect(mockFetch).toHaveBeenCalledWith(
      "https://getpocket.com/v3/oauth/authorize",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=UTF-8", "X-Accept": "application/json" },
        body: JSON.stringify({ consumer_key: "key1", code: "c1" }),
      },
    );
    expect(mockExecuteGraphQLQuery).toHaveBeenCalledWith(
      expect.stringContaining("InsertUserToken"),
      expect.objectContaining({ userId: "u1", service: "pocket", accessToken: "at1" }),
      "InsertUserToken",
      "u1",
    );
  });

  it("returns 500 when the token exchange fails", async () => {
    process.env.POCKET_CONSUMER_KEY = "key1";
    mockFetch.mockResolvedValue(httpResponse(false, 401, "denied"));
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await pocketCallback(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Failed to complete Pocket OAuth flow" });
  });

  it("returns 500 when fetch rejects", async () => {
    process.env.POCKET_CONSUMER_KEY = "key1";
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await pocketCallback(req, res);
    expect(res._getStatusCode()).toBe(500);
  });
});

describe("pages/api/quickbooks/oauth/callback", () => {
  const oldEnv = { ...process.env };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({ user: { id: "u1" } });
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    process.env.QUICKBOOKS_CLIENT_ID = "qb-id";
    process.env.QUICKBOOKS_CLIENT_SECRET = "qb-secret";
    process.env.QUICKBOOKS_REDIRECT_URI = "http://localhost:3000/cb";
    mockOAuthClient.mockImplementation(() => ({ createToken: mockCreateToken }));
  });

  afterEach(() => {
    process.env = { ...oldEnv };
  });

  it("returns 401 without a session", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await quickbooksCallback(req, res);
    expect(res._getStatusCode()).toBe(401);
  });

  it("stores tokens and redirects on success", async () => {
    mockCreateToken.mockResolvedValue({
      getJson: () => ({
        access_token: "at",
        refresh_token: "rt",
        expires_in: 3600,
        realmId: "realm1",
      }),
    });
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({ method: "GET", query: { code: "c" }, url: "/api/quickbooks/oauth/callback?code=c" }) as any;
    await quickbooksCallback(req, res);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations/quickbooks?success=true");
    expect(mockCreateToken).toHaveBeenCalledWith("/api/quickbooks/oauth/callback?code=c");
    const [, opts] = mockFetch.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body.user_id).toBe("u1");
    expect(body.access_token).toBe("at");
    expect(body.refresh_token).toBe("rt");
    expect(body.realm_id).toBe("realm1");
    expect(typeof body.expires_at).toBe("string");
  });

  it("returns 500 when the token exchange fails", async () => {
    mockCreateToken.mockRejectedValue(new Error("invalid grant"));
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await quickbooksCallback(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Failed to complete QuickBooks OAuth flow" });
  });

  it("returns 500 when storing tokens fails", async () => {
    mockCreateToken.mockResolvedValue({
      getJson: () => ({ access_token: "at", refresh_token: "rt", expires_in: 60, realmId: "r" }),
    });
    mockFetch.mockResolvedValue(httpResponse(false, 500, {}));
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await quickbooksCallback(req, res);
    expect(res._getStatusCode()).toBe(500);
  });
});
