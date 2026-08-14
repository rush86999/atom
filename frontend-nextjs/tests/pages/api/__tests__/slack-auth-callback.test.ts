const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/auth/slack/callback";

describe("pages/api/auth/slack/callback", () => {
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

  it("redirects with the provider error when Slack reports one", async () => {
    const res = await invoke({ error: "access_denied", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=access_denied");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with no_code when the authorization code is missing", async () => {
    const res = await invoke({ state: "s" });
    expect(res._getRedirectUrl()).toBe("/integrations?error=no_code");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with no_state when state is missing", async () => {
    const res = await invoke({ code: "c" });
    expect(res._getRedirectUrl()).toBe("/integrations?error=no_state");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with no_state when state is not a string", async () => {
    const res = await invoke({ code: "c", state: ["a", "b"] });
    expect(res._getRedirectUrl()).toBe("/integrations?error=no_state");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("exchanges the code with the backend and redirects on success", async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const res = await invoke(
      { code: "c-1", state: "st-1" },
      { cookie: "sid=xyz" },
    );
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations?success=true&provider=slack",
    );
    expect(mockFetch).toHaveBeenCalledWith("http://backend.test/api/slack/callback", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        cookie: "sid=xyz",
      },
      body: JSON.stringify({ code: "c-1", state: "st-1" }),
    });
  });

  it("uses the default backend URL when the env var is unset", async () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    mockFetch.mockResolvedValue({ ok: true });
    const res = await invoke({ code: "c", state: "s" });
    expect(res._getRedirectUrl()).toBe(
      "/integrations?success=true&provider=slack",
    );
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://localhost:8001/api/slack/callback",
    );
  });

  it("redirects with token_exchange_failed and detail when the backend rejects", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      text: async () => "invalid code provided",
    });
    const res = await invoke({ code: "bad", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "/integrations?error=token_exchange_failed&detail=" +
        encodeURIComponent("invalid code provided"),
    );
    expect(console.error).toHaveBeenCalledWith(
      "Token exchange failed:",
      "invalid code provided",
    );
  });

  it("truncates long backend error details to 100 characters", async () => {
    const longText = "x".repeat(250);
    mockFetch.mockResolvedValue({ ok: false, text: async () => longText });
    const res = await invoke({ code: "bad", state: "s" });
    expect(res._getRedirectUrl()).toBe(
      "/integrations?error=token_exchange_failed&detail=" +
        encodeURIComponent("x".repeat(100)),
    );
  });

  it("redirects with callback_exception when fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("dns failure"));
    const res = await invoke({ code: "c", state: "s" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=callback_exception");
  });
});
