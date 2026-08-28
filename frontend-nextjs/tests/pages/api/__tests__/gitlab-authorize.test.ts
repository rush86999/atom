const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/authorize";

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

describe("pages/api/integrations/gitlab/authorize", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (body?: any, method = "POST") => {
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when user_id is missing", async () => {
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "User ID is required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("initiates OAuth with default scopes and returns the authorization url", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ authorization_url: "https://gitlab.com/oauth/authorize?x=1" }),
    );
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      authorization_url: "https://gitlab.com/oauth/authorize?x=1",
      user_id: "user-1",
      success: true,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/gitlab/authorize",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          scopes: ["read_repository", "api", "read_user"],
          platform: "tauri",
        }),
      },
    );
  });

  it("forwards custom scopes when provided", async () => {
    mockFetch.mockResolvedValue(okResponse({ authorization_url: "https://gl" }));
    await invoke({ user_id: "user-2", scopes: ["read_user"] });
    const sentBody = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(sentBody.scopes).toEqual(["read_user"]);
  });

  it("honors NEXT_PUBLIC_API_BASE_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:9999";
    mockFetch.mockResolvedValue(okResponse({ authorization_url: "https://gl" }));
    await invoke({ user_id: "user-1" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:9999/api/auth/gitlab/authorize",
    );
  });

  it("mirrors the backend error and status when initiation fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(502, { error: "backend misconfigured" }),
    );
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "backend misconfigured",
    });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(500, {}));
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to initiate GitLab OAuth",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
