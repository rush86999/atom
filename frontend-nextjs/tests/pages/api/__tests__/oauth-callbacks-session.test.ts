const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));

import { createMocks } from "node-mocks-http";
import zoomStart from "@/pages/api/integrations/zoom/auth/start";
import salesforceStart from "@/pages/api/integrations/salesforce/auth/start";
import salesforceCallback from "@/pages/api/integrations/salesforce/callback";
import gmailCallback from "@/pages/api/integrations/gmail/callback";
import nextjsConfig from "@/pages/api/integrations/nextjs/config";

const mockFetch = jest.fn();
const httpResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
  text: async () => JSON.stringify(data),
});

describe("pages/api/integrations/zoom/auth/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({
      user: { name: "u" },
      backendToken: "ztok",
    });
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-GET with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await zoomStart(req, res);
    expect(res._getStatusCode()).toBe(405);
  });

  it("returns 401 when there is no session", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "GET" }) as any;
    await zoomStart(req, res);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Unauthorized" });
  });

  it("returns 401 when the backend token is missing", async () => {
    mockGetServerSession.mockResolvedValue({ user: { name: "u" } });
    const { req, res } = createMocks({ method: "GET" }) as any;
    await zoomStart(req, res);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Missing authentication token" });
  });

  it("redirects to the authorization URL returned by the backend", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { url: "https://zoom.us/oauth/authorize?x=1" }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await zoomStart(req, res);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("https://zoom.us/oauth/authorize?x=1");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/zoom/v1/auth/url",
      { headers: { Authorization: "Bearer ztok" } },
    );
  });

  it("returns 500 when the backend omits the url", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await zoomStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "No authorization URL returned from backend" });
  });

  it("returns 500 when the backend is not ok", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 500, {}));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await zoomStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to initiate Zoom OAuth flow" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await zoomStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to initiate Zoom OAuth flow" });
  });
});

describe("pages/api/integrations/salesforce/auth/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({
      user: { name: "u", id: "1" },
      backendToken: "stok",
    });
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("returns 401 when there is no session", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "GET" }) as any;
    await salesforceStart(req, res);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 401 when the backend token is missing", async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: "1" } });
    const { req, res } = createMocks({ method: "GET" }) as any;
    await salesforceStart(req, res);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Missing authentication token" });
  });

  it("redirects to the salesforce authorization URL", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { url: "https://login.salesforce.com/services/oauth2/authorize?y=2" }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await salesforceStart(req, res);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("https://login.salesforce.com/services/oauth2/authorize?y=2");
  });

  it("returns 500 when the backend returns no url", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await salesforceStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to get Salesforce authorization URL",
      message: "No authorization URL returned from backend",
    });
  });

  it("returns 500 when the backend responds with an error", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 503, {}));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await salesforceStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Backend Salesforce service error",
      message: "Failed to contact Salesforce authentication service",
    });
  });

  it("returns 500 with error message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("boom"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await salesforceStart(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to start Salesforce OAuth flow",
      message: "boom",
    });
  });
});

describe("pages/api/integrations/salesforce/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({
      user: { name: "u", id: "1" },
      backendToken: "stok",
    });
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("redirects to signin when the session is missing", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await salesforceCallback(req, res);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("/auth/signin?callbackUrl=/integrations/salesforce");
  });

  it("redirects to signin with missing token when backend token is absent", async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: "1" } });
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await salesforceCallback(req, res);
    expect(res._getRedirectUrl()).toContain("error=missing_token");
  });

  it("redirects with the oauth error when the backend reports one", async () => {
    const { req, res } = createMocks({ method: "GET", query: { error: "access_denied" } }) as any;
    await salesforceCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/salesforce?error=access_denied");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with missing_code when no code is provided", async () => {
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await salesforceCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/salesforce?error=missing_code");
  });

  it("exchanges the code and redirects on success", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({ method: "GET", query: { code: "c1", state: "s1" } }) as any;
    await salesforceCallback(req, res);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations/salesforce?success=true&connected=true");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/salesforce/callback?code=c1&state=s1",
      { method: "GET", headers: { Authorization: "Bearer stok" } },
    );
  });

  it("redirects with exchange_failed details on backend error", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 400, { detail: "invalid grant" }));
    const { req, res } = createMocks({ method: "GET", query: { code: "bad" } }) as any;
    await salesforceCallback(req, res);
    expect(res._getRedirectUrl()).toBe(
      "/integrations/salesforce?error=exchange_failed&details=invalid grant",
    );
  });

  it("redirects with unknown details when the error body is not json", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => { throw new Error("not json"); },
    });
    const { req, res } = createMocks({ method: "GET", query: { code: "bad" } }) as any;
    await salesforceCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/salesforce?error=exchange_failed&details=unknown");
  });

  it("redirects with server_error when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await salesforceCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/salesforce?error=server_error");
  });
});

describe("pages/api/integrations/gmail/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-GET with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await gmailCallback(req, res);
    expect(res._getStatusCode()).toBe(405);
  });

  it("redirects with auth_failed when the backend reports an oauth error", async () => {
    const { req, res } = createMocks({ method: "GET", query: { error: "denied" } }) as any;
    await gmailCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/gmail?error=auth_failed");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with missing_code when no code is provided", async () => {
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await gmailCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/gmail?error=missing_code");
  });

  it("exchanges the code and redirects on success", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { tokens: {} }));
    const { req, res } = createMocks({ method: "GET", query: { code: "c1", state: "st" } }) as any;
    await gmailCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/gmail?success=true");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/google/callback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: "c1", state: "st" }),
      },
    );
  });

  it("redirects with token_exchange_failed when the backend errors", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 400, { detail: "nope" }));
    const { req, res } = createMocks({ method: "GET", query: { code: "bad" } }) as any;
    await gmailCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/gmail?error=token_exchange_failed");
  });

  it("redirects with callback_failed when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: { code: "c" } }) as any;
    await gmailCallback(req, res);
    expect(res._getRedirectUrl()).toBe("/integrations/gmail?error=callback_failed");
  });
});

describe("pages/api/integrations/nextjs/config", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await nextjsConfig(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("returns 400 when user_id is missing", async () => {
    const { req, res } = createMocks({ method: "POST", body: { config: {} } }) as any;
    await nextjsConfig(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "User ID is required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 for an unknown action", async () => {
    const { req, res } = createMocks({ method: "POST", body: { user_id: "u1", action: "delete" } }) as any;
    await nextjsConfig(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Invalid action" });
  });

  it("saves the config for action=save", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { config: { key: "v" } }));
    const { req, res } = createMocks({
      method: "POST",
      body: { user_id: "u1", action: "save", config: { key: "v" } },
    }) as any;
    await nextjsConfig(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, config: { key: "v" }, message: "Configuration saved successfully" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/nextjs/config",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "u1", config: { key: "v" } }),
      },
    );
  });

  it("loads the config for action=load", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { config: { loaded: true } }));
    const { req, res } = createMocks({ method: "POST", body: { user_id: "u1", action: "load" } }) as any;
    await nextjsConfig(req, res);
    expect(res._getJSONData()).toEqual({ ok: true, config: { loaded: true }, message: "Configuration loadd successfully" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/nextjs/config",
      { method: "GET", headers: { "Content-Type": "application/json", "X-User-ID": "u1" } },
    );
  });

  it("mirrors backend errors with ok:false", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 500, { error: "backend failed" }));
    const { req, res } = createMocks({ method: "POST", body: { user_id: "u1", action: "save", config: {} } }) as any;
    await nextjsConfig(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ ok: false, error: "backend failed" });
  });

  it("defaults the error message when the backend omits it", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 500, {}));
    const { req, res } = createMocks({ method: "POST", body: { user_id: "u1", action: "load" } }) as any;
    await nextjsConfig(req, res);
    expect(res._getJSONData()).toEqual({ ok: false, error: "Failed to manage configuration" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "POST", body: { user_id: "u1", action: "save", config: {} } }) as any;
    await nextjsConfig(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ ok: false, error: "Internal server error" });
  });
});
