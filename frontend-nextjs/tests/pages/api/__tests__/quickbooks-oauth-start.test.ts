const mockAuthorizeUri = jest.fn();
const OAuthClientMock: any = jest.fn();

jest.mock("intuit-oauth", () => ({
  __esModule: true,
  default: OAuthClientMock,
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/quickbooks/oauth/start";

describe("pages/api/quickbooks/oauth/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    OAuthClientMock.prototype.authorizeUri = mockAuthorizeUri;
    OAuthClientMock.scopes = { Accounting: "com.intuit.quickbooks.accounting" };
    process.env.QUICKBOOKS_CLIENT_ID = "qb-client-id";
    process.env.QUICKBOOKS_CLIENT_SECRET = "qb-client-secret";
    process.env.QUICKBOOKS_REDIRECT_URI = "https://fe.atom.test/api/quickbooks/callback";
    delete process.env.QUICKBOOKS_ENVIRONMENT;
    mockAuthorizeUri.mockReturnValue(
      "https://appcenter.intuit.com/connect/oauth2",
    );
  });

  afterEach(() => {
    delete process.env.QUICKBOOKS_CLIENT_ID;
    delete process.env.QUICKBOOKS_CLIENT_SECRET;
    delete process.env.QUICKBOOKS_REDIRECT_URI;
    delete process.env.QUICKBOOKS_ENVIRONMENT;
  });

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    handler(req, res);
    return res;
  };

  it("builds an OAuth client with sandbox defaults and redirects to the authorize URI", async () => {
    const res = await invoke();
    expect(OAuthClientMock).toHaveBeenCalledWith({
      clientId: "qb-client-id",
      clientSecret: "qb-client-secret",
      environment: "sandbox",
      redirectUri: "https://fe.atom.test/api/quickbooks/callback",
    });
    expect(mockAuthorizeUri).toHaveBeenCalledWith({
      scope: ["com.intuit.quickbooks.accounting"],
      state: expect.any(String),
    });
    const state = mockAuthorizeUri.mock.calls[0][0].state as string;
    expect(state.length).toBeGreaterThan(0);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://appcenter.intuit.com/connect/oauth2",
    );
  });

  it("uses the configured environment when provided", async () => {
    process.env.QUICKBOOKS_ENVIRONMENT = "production";
    await invoke();
    expect(OAuthClientMock).toHaveBeenCalledWith(
      expect.objectContaining({ environment: "production" }),
    );
  });
});
