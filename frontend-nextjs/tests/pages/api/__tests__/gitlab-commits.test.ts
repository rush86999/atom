const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/commits";

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

describe("pages/api/integrations/gitlab/commits", () => {
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
    const res = await invoke({ project_id: "p-1" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "User ID and Project ID are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when project_id is missing", async () => {
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "User ID and Project ID are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("fetches commits with default branch and limit", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ commits: [{ id: "abc" }, { id: "def" }] }),
    );
    const res = await invoke({ user_id: "user-1", project_id: "p-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      commits: [{ id: "abc" }, { id: "def" }],
      total: 2,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/commits",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          project_id: "p-1",
          branch: "main",
          since: undefined,
          until: undefined,
          author: undefined,
          limit: 20,
        }),
      },
    );
  });

  it("forwards explicit filters to the backend", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:8888";
    mockFetch.mockResolvedValue(okResponse({ commits: [] }));
    await invoke({
      user_id: "u",
      project_id: "p",
      branch: "develop",
      since: "2026-01-01",
      until: "2026-02-01",
      author: "octocat",
      limit: 5,
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:8888/api/integrations/gitlab/commits",
    );
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      branch: "develop",
      since: "2026-01-01",
      until: "2026-02-01",
      author: "octocat",
      limit: 5,
    });
  });

  it("defaults to an empty commit list when the backend returns none", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke({ user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, commits: [], total: 0 });
  });

  it("mirrors the backend error and status when the fetch fails", async () => {
    mockFetch.mockResolvedValue(failingResponse(403, { error: "Forbidden" }));
    const res = await invoke({ user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(403);
    expect(res._getJSONData()).toEqual({ ok: false, error: "Forbidden" });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(500, {}));
    const res = await invoke({ user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to fetch GitLab commits",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("socket hang up"));
    const res = await invoke({ user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
