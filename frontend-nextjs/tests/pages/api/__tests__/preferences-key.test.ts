const mockFetch = jest.fn();

function backendResponse(
  ok: boolean,
  data: any,
  status = ok ? 200 : 500,
): any {
  return {
    ok,
    status,
    json: async () => data,
    text: async () => (typeof data === "string" ? data : JSON.stringify(data)),
  };
}

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/preferences/[key]";

describe("pages/api/preferences/[key]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (
    method: any = "GET",
    query: any = {},
    headers: any = {},
  ) => {
    const { req, res } = createMocks({ method, query, headers }) as any;
    await handler(req, res);
    return res;
  };

  it("forwards a GET with default user/workspace and returns the preference", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(true, { key: "theme", value: "dark" }),
    );
    const res = await invoke("GET", { key: "theme" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ key: "theme", value: "dark" });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/v1/preferences/theme?");
    expect(url).toContain("user_id=default_user");
    expect(url).toContain("workspace_id=default");
    expect(init.headers).toEqual({
      Authorization: "Bearer ",
      "Content-Type": "application/json",
    });
  });

  it("forwards the provided user, workspace and bearer token", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { value: 7 }));
    const res = await invoke(
      "GET",
      { key: "refresh_interval", user_id: "u-9", workspace_id: "ws-2" },
      { authorization: "Bearer tok-123" },
    );
    expect(res._getStatusCode()).toBe(200);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/v1/preferences/refresh_interval?");
    expect(url).toContain("user_id=u-9");
    expect(url).toContain("workspace_id=ws-2");
    expect(init.headers).toEqual({
      Authorization: "Bearer tok-123",
      "Content-Type": "application/json",
    });
  });

  it("passes through the backend status and error text when not ok", async () => {
    mockFetch.mockResolvedValue(backendResponse(false, "preference missing", 404));
    const res = await invoke("GET", { key: "nope" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "preference missing" });
  });

  it("returns 500 when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("GET", { key: "theme" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to fetch preference" });
    expect(console.error).toHaveBeenCalledWith(
      "Get preference error:",
      expect.any(Error),
    );
  });

  it("returns 405 for non-GET methods", async () => {
    const res = await invoke("POST", { key: "theme" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
