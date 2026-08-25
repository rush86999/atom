const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/projects";

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

describe("pages/api/integrations/gitlab/projects", () => {
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

  it("fetches projects with default filters", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        projects: [{ id: 1, name: "repo-a" }],
        pipelines: [{ id: 11 }],
        issues: [{ iid: 21 }],
        merge_requests: [{ iid: 31 }],
      }),
    );
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      projects: [{ id: 1, name: "repo-a" }],
      pipelines: [{ id: 11 }],
      issues: [{ iid: 21 }],
      merge_requests: [{ iid: 31 }],
      total: 1,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/projects",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          limit: 50,
          visibility: "all",
          archived: false,
          search: undefined,
          sort: "updated_at",
          order: "desc",
          include_pipelines: true,
          include_issues: true,
          include_merge_requests: true,
        }),
      },
    );
  });

  it("forwards explicit filters and honors NEXT_PUBLIC_API_BASE_URL", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:5151";
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke({
      user_id: "u",
      limit: 5,
      visibility: "private",
      archived: true,
      search: "atom",
      sort: "name",
      order: "asc",
      include_pipelines: false,
      include_issues: false,
      include_merge_requests: false,
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5151/api/integrations/gitlab/projects",
    );
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      limit: 5,
      visibility: "private",
      archived: true,
      search: "atom",
      sort: "name",
      order: "asc",
      include_pipelines: false,
      include_issues: false,
      include_merge_requests: false,
    });
  });

  it("defaults every collection to an empty list when the backend returns none", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      projects: [],
      pipelines: [],
      issues: [],
      merge_requests: [],
      total: 0,
    });
  });

  it("mirrors the backend error and status when the fetch fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(401, { error: "Invalid GitLab token" }),
    );
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Invalid GitLab token",
    });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(503, {}));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to fetch GitLab projects",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("backend down"));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
