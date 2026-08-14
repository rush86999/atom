const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

const mockGetAuthCodeUrl = jest.fn();
jest.mock("@azure/msal-node", () => ({
  __esModule: true,
  PublicClientApplication: jest.fn(() => ({ getAuthCodeUrl: mockGetAuthCodeUrl })),
  ConfidentialClientApplication: jest.fn(),
  LogLevel: { Error: 0, Warning: 1, Info: 2, Verbose: 3, Trace: 4 },
}));

jest.mock("@lib/logger", () => ({
  logger: {
    info: jest.fn(),
    error: jest.fn(),
    warn: jest.fn(),
    debug: jest.fn(),
  },
}));

import { createMocks } from "node-mocks-http";
import unconfiguredHandler from "@/pages/api/atom/auth/msteams/initiate";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/atom/auth/msteams/initiate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.MSTEAMS_CLIENT_ID;
    delete process.env.MSTEAMS_CLIENT_SECRET;
    delete process.env.MSTEAMS_REDIRECT_URI;
    mockGetServerSession.mockResolvedValue(mockSession);
  });

  afterEach(() => {
    delete process.env.MSTEAMS_CLIENT_ID;
    delete process.env.MSTEAMS_CLIENT_SECRET;
    delete process.env.MSTEAMS_REDIRECT_URI;
    jest.resetModules();
  });

  const invoke = async (
    session: any = mockSession,
    handlerFn: any = unconfiguredHandler,
  ) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handlerFn(req, res);
    return res;
  };

  it("returns 401 when unauthenticated", async () => {
    const res = await invoke(null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Authentication required." });
    expect(mockGetAuthCodeUrl).not.toHaveBeenCalled();
  });

  it("returns 401 when the session has no user", async () => {
    const res = await invoke({ expires: "soon" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Authentication required." });
  });

  it("returns 500 when the MS Teams client id is not configured", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "MS Teams OAuth configuration error on server.",
    });
    expect(mockGetAuthCodeUrl).not.toHaveBeenCalled();
  });

  describe("with configured credentials", () => {
    let configuredHandler: any;

    beforeEach(async () => {
      process.env.MSTEAMS_CLIENT_ID = "client-1";
      process.env.MSTEAMS_CLIENT_SECRET = "secret-1";
      jest.resetModules();
      configuredHandler = (await import("@/pages/api/atom/auth/msteams/initiate"))
        .default;
    });

    it("redirects to the MS Teams auth code URL with the user id as state", async () => {
      mockGetAuthCodeUrl.mockResolvedValue(
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=client-1",
      );
      const res = await invoke(mockSession, configuredHandler);
      expect(res._getStatusCode()).toBe(302);
      expect(res._getRedirectUrl()).toBe(
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=client-1",
      );
      expect(mockGetAuthCodeUrl).toHaveBeenCalledWith(
        expect.objectContaining({
          redirectUri: "http://localhost:3000/api/atom/auth/msteams/callback",
          state: "user-1",
          prompt: "select_account",
          scopes: expect.arrayContaining(["Chat.Read", "offline_access"]),
        }),
      );
    });

    it("invokes the MSAL logger callback from the config without throwing", async () => {
      mockGetAuthCodeUrl.mockResolvedValue("https://login.microsoftonline.com/auth");
      await invoke(mockSession, configuredHandler);
      // After jest.resetModules() the handler re-imports a fresh (mocked)
      // msal-node module, so read the constructor calls from that instance.
      const msal = (await import("@azure/msal-node")) as any;
      const msalConfig = msal.PublicClientApplication.mock.calls[0][0];
      expect(msalConfig.auth.clientId).toBe("client-1");
      expect(() =>
        msalConfig.system.loggerOptions.loggerCallback(1, "msal log", false),
      ).not.toThrow();
    });

    it("returns 500 when generating the auth URL fails", async () => {
      mockGetAuthCodeUrl.mockRejectedValue(new Error("url generation failed"));
      const res = await invoke(mockSession, configuredHandler);
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        message: "Failed to initiate MS Teams authentication.",
      });
      const { logger } = await import("@lib/logger");
      expect(logger.error).toHaveBeenCalledWith(
        expect.any(String),
        "url generation failed",
      );
    });

    it("stringifies non-Error rejections for logging", async () => {
      mockGetAuthCodeUrl.mockRejectedValue("plain failure");
      const res = await invoke(mockSession, configuredHandler);
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        message: "Failed to initiate MS Teams authentication.",
      });
      const { logger } = await import("@lib/logger");
      expect(logger.error).toHaveBeenCalledWith(
        expect.any(String),
        "plain failure",
      );
    });
  });
});
