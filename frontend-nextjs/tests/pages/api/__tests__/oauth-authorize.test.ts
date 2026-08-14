import { createMocks } from "node-mocks-http";
import bitbucketAuthorize from "@/pages/api/integrations/bitbucket/authorize";
import mondayAuthorize from "@/pages/api/integrations/monday/authorize";

const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));

describe("pages/api/integrations/bitbucket/authorize", () => {
  const oldEnv = { ...process.env };

  afterEach(() => {
    process.env = { ...oldEnv };
    jest.restoreAllMocks();
  });

  it("rejects non-GET methods with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await bitbucketAuthorize(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("returns 500 when the client ID is not configured", async () => {
    delete process.env.BITBUCKET_CLIENT_ID;
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await bitbucketAuthorize(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Bitbucket client ID not configured",
      details: "Please set BITBUCKET_CLIENT_ID environment variable",
    });
  });

  it("builds an authorization URL with the configured client id", async () => {
    process.env.BITBUCKET_CLIENT_ID = "bb-client";
    process.env.BITBUCKET_REDIRECT_URI = "http://localhost:3000/api/integrations/bitbucket/callback";
    const { req, res } = createMocks({ method: "GET", query: { state: "s1" } }) as any;
    await bitbucketAuthorize(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.state).toBe("s1");
    const url = new URL(body.authorization_url);
    expect(url.origin + url.pathname).toBe("https://bitbucket.org/site/oauth2/authorize");
    expect(url.searchParams.get("client_id")).toBe("bb-client");
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost:3000/api/integrations/bitbucket/callback");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("scope")).toBe("repository team account");
    expect(url.searchParams.get("state")).toBe("s1");
  });

  it("defaults the state and redirect URI when omitted", async () => {
    process.env.BITBUCKET_CLIENT_ID = "bb-client";
    delete process.env.BITBUCKET_REDIRECT_URI;
    process.env.NEXTAUTH_URL = "http://localhost:3000";
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await bitbucketAuthorize(req, res);
    const body = res._getJSONData();
    expect(body.state).toBe("default");
    const url = new URL(body.authorization_url);
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost:3000/api/integrations/bitbucket/callback");
    expect(url.searchParams.get("state")).toBe("default");
  });
});

describe("pages/api/integrations/monday/authorize", () => {
  const oldEnv = { ...process.env };

  afterEach(() => {
    process.env = { ...oldEnv };
    jest.restoreAllMocks();
  });

  it("rejects non-GET methods with 405", async () => {
    const { req, res } = createMocks({ method: "PUT" }) as any;
    await mondayAuthorize(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("returns 500 when the client ID is not configured", async () => {
    delete process.env.MONDAY_CLIENT_ID;
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await mondayAuthorize(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Monday.com client ID not configured",
      details: "Please set MONDAY_CLIENT_ID environment variable",
    });
  });

  it("builds an authorization URL with the configured client id", async () => {
    process.env.MONDAY_CLIENT_ID = "monday-client";
    process.env.MONDAY_REDIRECT_URI = "http://localhost:3000/api/integrations/monday/callback";
    const { req, res } = createMocks({ method: "GET", query: { state: "xyz" } }) as any;
    await mondayAuthorize(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.state).toBe("xyz");
    const url = new URL(body.authorization_url);
    expect(url.origin + url.pathname).toBe("https://auth.monday.com/oauth2/authorize");
    expect(url.searchParams.get("client_id")).toBe("monday-client");
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost:3000/api/integrations/monday/callback");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("scope")).toBe("boards:read boards:write workspaces:read users:read");
    expect(url.searchParams.get("state")).toBe("xyz");
  });

  it("defaults state and redirect URI when omitted", async () => {
    process.env.MONDAY_CLIENT_ID = "monday-client";
    delete process.env.MONDAY_REDIRECT_URI;
    process.env.NEXTAUTH_URL = "http://localhost:3000";
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await mondayAuthorize(req, res);
    const body = res._getJSONData();
    expect(body.state).toBe("default");
    const url = new URL(body.authorization_url);
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost:3000/api/integrations/monday/callback");
  });
});
