const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/auth/github/callback";

function backendResponse(ok: boolean, text: string, status = ok ? 200 : 400): any {
  return { ok, status, text: async () => text };
}

describe("pages/api/auth/github/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  const invoke = async (query: any = {}) => {
    const { req, res } = createMocks({ method: "GET", query }) as any;
    await handler(req, res);
    return res;
  };

  it("redirects with the provider error when one is reported", async () => {
    const res = await invoke({ error: "access_denied" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=access_denied");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects with no_code when the code is missing", async () => {
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=no_code");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("exchanges the code with the backend and redirects on success", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, '{"ok":true}'));
    const res = await invoke({ code: "gh-code" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?success=true&provider=github");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8001/api/auth/github/callback");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({
      code: "gh-code",
      redirect_uri: "http://localhost:3000/api/auth/github/callback",
    });
  });

  it("redirects with token_exchange_failed and logs when the backend rejects the code", async () => {
    mockFetch.mockResolvedValue(backendResponse(false, "bad_verification_code", 400));
    const res = await invoke({ code: "bad" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=token_exchange_failed");
    expect(console.error).toHaveBeenCalledWith(
      "Token exchange failed:",
      "bad_verification_code",
    );
  });

  it("redirects with callback_exception when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke({ code: "gh-code" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations?error=callback_exception");
    expect(console.error).toHaveBeenCalledWith(
      "OAuth callback error:",
      expect.any(Error),
    );
  });
});
