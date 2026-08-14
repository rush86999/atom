const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/auth/gmail/callback";

describe("pages/api/auth/gmail/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend.test";
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  const invoke = async (query: any = {}, headers: any = {}) => {
    const { req, res } = createMocks({ method: "GET", query, headers }) as any;
    await handler(req, res);
    return res;
  };

  it("redirects with the provider error when Google reports one", async () => {
    const res = await invoke({ error: "access_denied", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=access_denied");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with no_code when the authorization code is missing", async () => {
    const res = await invoke({ state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=no_code");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with no_state when state is missing", async () => {
    const res = await invoke({ code: "c" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=no_state");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with no_state when state is not a string", async () => {
    const res = await invoke({ code: "c", state: ["s1", "s2"] });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=no_state");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("exchanges the code with the backend and redirects on success", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    const res = await invoke(
      { code: "c-1", state: "st-1" },
      { cookie: "sid=abc" },
    );
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations?success=true&provider=google",
    );
    expect(mockFetch).toHaveBeenCalledWith(
      "http://backend.test/api/gmail/callback",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          cookie: "sid=abc",
        },
        body: JSON.stringify({
          code: "c-1",
          state: "st-1",
          redirect_uri: "http://localhost:3000/api/auth/gmail/callback",
        }),
      },
    );
  });

  it("forwards an empty cookie header when the request has none", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke({ code: "c", state: "s" });
    expect(res._getRedirectUrl()).toBe(
      "/integrations?success=true&provider=google",
    );
    expect((mockFetch.mock.calls[0][1] as any).headers.cookie).toBe("");
  });

  it("uses the default backend URL when the env var is unset", async () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const res = await invoke({ code: "c", state: "s" });
    expect(res._getRedirectUrl()).toBe(
      "/integrations?success=true&provider=google",
    );
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://localhost:8001/api/gmail/callback",
    );
  });

  it("redirects with token_exchange_failed when the backend rejects the code", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      text: async () => "invalid grant",
    });
    const res = await invoke({ code: "bad", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations?error=token_exchange_failed",
    );
    expect(console.error).toHaveBeenCalledWith(
      "Token exchange failed:",
      "invalid grant",
    );
  });

  it("redirects with callback_exception when fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke({ code: "c", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=callback_exception");
    expect(console.error).toHaveBeenCalledWith(
      "OAuth callback error:",
      expect.any(Error),
    );
  });
});
