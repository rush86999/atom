const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/merge-requests";

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

describe("pages/api/integrations/gitlab/merge-requests", () => {
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

  it("fetches merge requests with default state and limit", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ merge_requests: [{ iid: 1 }, { iid: 2 }, { iid: 3 }] }),
    );
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      merge_requests: [{ iid: 1 }, { iid: 2 }, { iid: 3 }],
      total: 3,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/merge-requests",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          project_id: undefined,
          state: "opened",
          source_branch: undefined,
          target_branch: undefined,
          author: undefined,
          assignee: undefined,
          labels: undefined,
          milestone: undefined,
          limit: 100,
        }),
      },
    );
  });

  it("forwards explicit filters and honors NEXT_PUBLIC_API_BASE_URL", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:2222";
    mockFetch.mockResolvedValue(okResponse({ merge_requests: [] }));
    await invoke({
      user_id: "u",
      project_id: "p",
      state: "merged",
      source_branch: "feature/y",
      target_branch: "develop",
      author: "octocat",
      assignee: "me",
      labels: "backend",
      milestone: "m1",
      limit: 25,
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:2222/api/integrations/gitlab/merge-requests",
    );
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      state: "merged",
      source_branch: "feature/y",
      target_branch: "develop",
      author: "octocat",
      assignee: "me",
      labels: "backend",
      milestone: "m1",
      limit: 25,
    });
  });

  it("defaults to an empty merge request list when the backend returns none", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      merge_requests: [],
      total: 0,
    });
  });

  it("mirrors the backend error and status when the fetch fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(404, { error: "Project not found" }),
    );
    const res = await invoke({ user_id: "u", project_id: "missing" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Project not found",
    });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(500, {}));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to fetch GitLab merge requests",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("econnrefused"));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
