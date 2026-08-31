const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/callback";

const okResponse = (data: any): any => ({
  ok: true,
  status: 200,
  json: async () => data,
});

const failingResponse = (status: number, data: any): any => ({
  ok: false,
  status,
  json: async () => data,
});

describe("pages/api/integrations/gitlab/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (body?: any, method: RequestMethod = "POST") => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when code is missing", async () => {
    const res = await invoke({ state: "user-1" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Code and state are required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when state is missing", async () => {
    const res = await invoke({ code: "oauth-code" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Code and state are required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("exchanges the code via the backend and returns the linked user", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        user_id: "user-1",
        user: { username: "octocat" },
        projects: [{ id: 1 }],
      }),
    );
    const res = await invoke({ code: "oauth-code", state: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      user_id: "user-1",
      user: { username: "octocat" },
      projects: [{ id: 1 }],
      success: true,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/gitlab/callback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: "oauth-code", state: "user-1" }),
      },
    );
  });

  it("honors NEXT_PUBLIC_API_BASE_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:1234";
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke({ code: "c", state: "s" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:1234/api/auth/gitlab/callback",
    );
  });

  it("mirrors the backend error and status when the exchange fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(400, { error: "invalid_grant" }),
    );
    const res = await invoke({ code: "bad", state: "s" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ ok: false, error: "invalid_grant" });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(502, {}));
    const res = await invoke({ code: "c", state: "s" });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "OAuth callback failed",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("dns failure"));
    const res = await invoke({ code: "c", state: "s" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
