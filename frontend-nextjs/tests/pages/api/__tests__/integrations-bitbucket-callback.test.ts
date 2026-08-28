const mockAxiosPost = jest.fn();
jest.mock("axios", () => ({
  __esModule: true,
  default: { post: mockAxiosPost },
}));

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/bitbucket/callback";

describe("pages/api/integrations/bitbucket/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    process.env.BITBUCKET_CLIENT_ID = "bb-client-id";
    process.env.BITBUCKET_CLIENT_SECRET = "bb-client-secret";
    delete process.env.BITBUCKET_REDIRECT_URI;
    process.env.NEXTAUTH_URL = "http://localhost:3000";
    mockAxiosPost.mockResolvedValue({
      data: {
        access_token: "bb-at",
        refresh_token: "bb-rt",
        expires_in: 3600,
        token_type: "bearer",
        scope: "repository",
      },
    });
  });

  afterEach(() => {
    delete process.env.BITBUCKET_CLIENT_ID;
    delete process.env.BITBUCKET_CLIENT_SECRET;
    delete process.env.BITBUCKET_REDIRECT_URI;
    delete process.env.NEXTAUTH_URL;
  });

  const invoke = async (query: any = {}, method = "GET") => {
    const { req, res } = createMocks({ method: method as RequestMethod, query }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke({ code: "c" }, "POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockAxiosPost).not.toHaveBeenCalled();
  });

  it("redirects back with the provider error", async () => {
    const res = await invoke({ error: "access_denied", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations/bitbucket?error=access_denied",
    );
    expect(mockAxiosPost).not.toHaveBeenCalled();
  });

  it("redirects with missing_authorization_code when no code is present", async () => {
    const res = await invoke({ state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations/bitbucket?error=missing_authorization_code",
    );
  });

  it("redirects with missing_credentials when env vars are unset", async () => {
    delete process.env.BITBUCKET_CLIENT_ID;
    const res = await invoke({ code: "auth-code", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations/bitbucket?error=missing_credentials",
    );
    expect(mockAxiosPost).not.toHaveBeenCalled();
  });

  it("exchanges the code and redirects with the tokens", async () => {
    const res = await invoke({ code: "auth-code", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "http://localhost:3000/integrations/bitbucket?success=true&access_token=bb-at&refresh_token=bb-rt&expires_in=3600&token_type=bearer&scope=repository",
    );
    expect(mockAxiosPost).toHaveBeenCalledWith(
      "https://bitbucket.org/site/oauth2/access_token",
      expect.any(URLSearchParams),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: expect.stringContaining("Basic "),
        }),
      }),
    );
  });

  it("prefers BITBUCKET_REDIRECT_URI over the NEXTAUTH_URL default", async () => {
    process.env.BITBUCKET_REDIRECT_URI = "http://custom/redirect";
    await invoke({ code: "auth-code", state: "s" });
    const body = mockAxiosPost.mock.calls[0][1] as URLSearchParams;
    expect(body.get("redirect_uri")).toBe("http://custom/redirect");
  });

  it("redirects with the upstream error code when the token exchange fails", async () => {
    mockAxiosPost.mockRejectedValue({
      response: { data: { error: "invalid_grant" } },
    });
    const res = await invoke({ code: "bad-code", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations/bitbucket?error=invalid_grant",
    );
    expect(console.error).toHaveBeenCalled();
  });

  it("redirects with api_error when the upstream error has no code", async () => {
    mockAxiosPost.mockRejectedValue({ response: { status: 500, data: {} } });
    const res = await invoke({ code: "auth-code", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations/bitbucket?error=api_error");
  });

  it("redirects with authentication_failed when the request throws", async () => {
    mockAxiosPost.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke({ code: "auth-code", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations/bitbucket?error=authentication_failed",
    );
    expect(console.error).toHaveBeenCalled();
  });
});
