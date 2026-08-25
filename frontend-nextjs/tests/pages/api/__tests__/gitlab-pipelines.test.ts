const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/pipelines";

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

describe("pages/api/integrations/gitlab/pipelines", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (body?: any, method = "POST") => {
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

  it("returns 400 when user_id is missing", async () => {
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "User ID is required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("fetches pipelines with default limit and include_jobs", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ pipelines: [{ id: 1, status: "success" }] }),
    );
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      pipelines: [{ id: 1, status: "success" }],
      total: 1,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/pipelines",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          project_id: undefined,
          status: undefined,
          ref: undefined,
          limit: 100,
          include_jobs: true,
        }),
      },
    );
  });

  it("forwards explicit filters and honors NEXT_PUBLIC_API_BASE_URL", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:7777";
    mockFetch.mockResolvedValue(okResponse({ pipelines: [] }));
    await invoke({
      user_id: "u",
      project_id: "p",
      status: "failed",
      ref: "refs/heads/main",
      limit: 10,
      include_jobs: false,
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:7777/api/integrations/gitlab/pipelines",
    );
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      status: "failed",
      ref: "refs/heads/main",
      limit: 10,
      include_jobs: false,
    });
  });

  it("defaults to an empty pipeline list when the backend returns none", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, pipelines: [], total: 0 });
  });

  it("mirrors the backend error and status when the fetch fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(429, { error: "Rate limit exceeded" }),
    );
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(429);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Rate limit exceeded",
    });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(500, {}));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to fetch GitLab pipelines",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("gateway timeout"));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
