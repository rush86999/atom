const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

const mockAcquireTokenByCode = jest.fn();
jest.mock("@azure/msal-node", () => ({
  ConfidentialClientApplication: jest.fn().mockImplementation(() => ({
    acquireTokenByCode: mockAcquireTokenByCode,
  })),
  LogLevel: {},
}));

const mockExecuteGraphQLMutation = jest.fn();
jest.mock("@/lib/graphqlClient", () => ({
  executeGraphQLMutation: mockExecuteGraphQLMutation,
}));

const mockConstants = {
  postgraphileGraphUrl: "http://localhost:3000/api/graphql",
  postgraphileAdminSecret: "admin-secret",
};
jest.mock("@/lib/constants", () => mockConstants);

const mockEncryptToken = jest.fn((t: string) => `enc:${t}`);
const mockGetEncryptionService = jest.fn(() => ({}));
jest.mock("@/lib/tokenEncryption", () => ({
  encryptToken: mockEncryptToken,
  getEncryptionService: mockGetEncryptionService,
}));

jest.mock("@/lib/logger", () => ({
  logger: { info: jest.fn(), error: jest.fn(), warn: jest.fn() },
}));

import { createMocks } from "node-mocks-http";
import unconfiguredHandler from "@/pages/api/atom/auth/msteams/callback";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

const msalSuccessResponse = {
  accessToken: "at-ms",
  refreshToken: "rt-ms",
  idToken: "id-tok",
  expiresOn: new Date("2099-01-01T00:00:00Z"),
  scopes: ["Chat.Read", "User.Read"],
  account: {
    homeAccountId: "ha-1",
    environment: "login.microsoftonline.com",
    tenantId: "t-1",
    username: "u@example.com",
  },
};

describe("pages/api/atom/auth/msteams/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    mockConstants.postgraphileGraphUrl = "http://localhost:3000/api/graphql";
    mockConstants.postgraphileAdminSecret = "admin-secret";
    mockEncryptToken.mockImplementation((t: string) => `enc:${t}`);
  });

  afterEach(() => {
    delete process.env.MSTEAMS_CLIENT_ID;
    delete process.env.MSTEAMS_CLIENT_SECRET;
    delete process.env.MSTEAMS_REDIRECT_URI;
    jest.resetModules();
  });

  const invoke = async (
    query: any,
    session: any = mockSession,
    handlerFn: any = unconfiguredHandler,
  ) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method: "GET", query }) as any;
    await handlerFn(req, res);
    return res;
  };

  it("redirects to login when unauthenticated", async () => {
    const res = await invoke({ code: "c", state: "user-1" }, null);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain(
      "/Auth/UserLogin?error=session_expired_oauth",
    );
  });

  it("rejects a state/session mismatch with 400", async () => {
    const res = await invoke({ code: "c", state: "other-user" });
    expect(res._getRedirectUrl()).toContain(
      "msteams_auth_error=invalid_state",
    );
  });

  it("redirects with the provider error when MS Identity reports an error", async () => {
    const res = await invoke({ error: "access_denied", state: "user-1" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("msteams_auth_error=access_denied");
  });

  it("redirects when no code is present", async () => {
    const res = await invoke({ state: "user-1" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("msteams_auth_error=no_code");
  });

  it("returns 500 when MS Teams client credentials are not configured", async () => {
    const res = await invoke({ code: "c", state: "user-1" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().message).toContain("configuration error");
    expect(mockAcquireTokenByCode).not.toHaveBeenCalled();
  });

  describe("with configured credentials", () => {
    let configuredHandler: any;

    beforeEach(async () => {
      process.env.MSTEAMS_CLIENT_ID = "client-1";
      process.env.MSTEAMS_CLIENT_SECRET = "secret-1";
      process.env.MSTEAMS_REDIRECT_URI = "http://localhost:3000/api/atom/auth/msteams/callback";
      jest.resetModules();
      configuredHandler = (await import("@/pages/api/atom/auth/msteams/callback"))
        .default;
    });

    it("stores tokens and redirects with success", async () => {
      mockAcquireTokenByCode.mockResolvedValue(msalSuccessResponse);
      mockExecuteGraphQLMutation.mockResolvedValue({
        insert_user_tokens: { affected_rows: 1 },
      });
      const res = await invoke(
        { code: "c-valid", state: "user-1" },
        mockSession,
        configuredHandler,
      );
      expect(res._getStatusCode()).toBe(302);
      expect(res._getRedirectUrl()).toContain("msteams_auth_success=true");
      expect(mockEncryptToken).toHaveBeenCalledWith("at-ms");
      const mutationCall = mockExecuteGraphQLMutation.mock.calls[0];
      expect(mutationCall[0]).toContain("UpsertUserToken");
      expect(mutationCall[1].objects[0]).toMatchObject({
        user_id: "user-1",
        service_name: "msteams_graph",
        access_token: "enc:at-ms",
        refresh_token: "enc:rt-ms",
        id_token: "enc:id-tok",
        token_type: "Bearer",
      });
    });

    it("redirects with an error when MSAL returns no access token", async () => {
      mockAcquireTokenByCode.mockResolvedValue({});
      const res = await invoke(
        { code: "c", state: "user-1" },
        mockSession,
        configuredHandler,
      );
      expect(res._getStatusCode()).toBe(302);
      expect(res._getRedirectUrl()).toContain(
        encodeURIComponent("Failed to acquire MS Teams token."),
      );
    });

    it("redirects with the save error when token persistence fails", async () => {
      mockAcquireTokenByCode.mockResolvedValue(msalSuccessResponse);
      mockExecuteGraphQLMutation.mockResolvedValue({
        insert_user_tokens: { affected_rows: 0 },
      });
      const res = await invoke(
        { code: "c", state: "user-1" },
        mockSession,
        configuredHandler,
      );
      expect(res._getStatusCode()).toBe(302);
      expect(res._getRedirectUrl()).toContain(
        encodeURIComponent("Token save did not affect any rows."),
      );
    });

    it("redirects with the MSAL error message when token acquisition throws", async () => {
      mockAcquireTokenByCode.mockRejectedValue(
        new Error("AADSTS7000218: bad secret"),
      );
      const res = await invoke(
        { code: "c", state: "user-1" },
        mockSession,
        configuredHandler,
      );
      expect(res._getStatusCode()).toBe(302);
      expect(res._getRedirectUrl()).toContain(
        encodeURIComponent("AADSTS7000218: bad secret"),
      );
    });

    it("redirects with config error when GraphQL is not configured", async () => {
      mockConstants.postgraphileGraphUrl = "";
      mockAcquireTokenByCode.mockResolvedValue(msalSuccessResponse);
      const res = await invoke(
        { code: "c", state: "user-1" },
        mockSession,
        configuredHandler,
      );
      expect(res._getStatusCode()).toBe(302);
      expect(res._getRedirectUrl()).toContain(
        encodeURIComponent("GraphQL client is not configured."),
      );
    });
  });
});
