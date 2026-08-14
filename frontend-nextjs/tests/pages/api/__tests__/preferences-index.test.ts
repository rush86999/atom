const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/preferences";

function backendJson(body: any, ok = true, status = 200): any {
  return { ok, status, json: async () => body };
}

function backendError(status: number, text: string): any {
  return { ok: false, status, text: async () => text };
}

describe("pages/api/preferences", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (
    method: any,
    options: { query?: any; body?: any; auth?: string | null } = {},
  ) => {
    const { query, body } = options;
    const auth = "auth" in options ? options.auth : "Bearer pref-token";
    const { req, res } = createMocks({
      method,
      query,
      body,
      headers: auth ? { authorization: auth } : {},
    }) as any;
    await handler(req, res);
    return res;
  };

  it("fetches preferences with default query params when none are given", async () => {
    mockFetch.mockResolvedValue(backendJson({ theme: "dark" }));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ theme: "dark" });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain(
      "/api/v1/preferences?user_id=default_user&workspace_id=default",
    );
    expect(init.headers.Authorization).toBe("Bearer pref-token");
  });

  it("forwards user_id and workspace_id query params on GET", async () => {
    mockFetch.mockResolvedValue(backendJson({ theme: "light" }));
    const res = await invoke("GET", {
      query: { user_id: "u-9", workspace_id: "ws-2" },
    });
    expect(res._getStatusCode()).toBe(200);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("user_id=u-9");
    expect(url).toContain("workspace_id=ws-2");
  });

  it("sends an empty bearer token on GET when no auth header is present", async () => {
    mockFetch.mockResolvedValue(backendJson({}));
    await invoke("GET", { auth: undefined });
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer ");
  });

  it("passes through the backend status and text on a failed GET", async () => {
    mockFetch.mockResolvedValue(backendError(404, "preferences not found"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "preferences not found" });
  });

  it("returns 500 when the GET request fails", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to fetch preferences" });
  });

  it("saves a preference with POST and returns the backend payload", async () => {
    mockFetch.mockResolvedValue(backendJson({ saved: true }));
    const res = await invoke("POST", { body: { theme: "solarized" } });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ saved: true });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/v1/preferences");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer pref-token");
    expect(JSON.parse(init.body)).toEqual({ theme: "solarized" });
  });

  it("passes through the backend status and text on a failed POST", async () => {
    mockFetch.mockResolvedValue(backendError(422, "invalid preference"));
    const res = await invoke("POST", { body: {} });
    expect(res._getStatusCode()).toBe(422);
    expect(res._getJSONData()).toEqual({ error: "invalid preference" });
  });

  it("returns 500 when the POST request fails", async () => {
    mockFetch.mockRejectedValue(new Error("socket hang up"));
    const res = await invoke("POST", { body: {} });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to save preference" });
  });

  it("rejects unsupported methods with 405", async () => {
    const res = await invoke("DELETE");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
