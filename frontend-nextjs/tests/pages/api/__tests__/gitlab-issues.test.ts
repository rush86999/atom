const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/issues";

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

describe("pages/api/integrations/gitlab/issues", () => {
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

  it("fetches issues with default state and limit", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ issues: [{ iid: 1 }, { iid: 2 }] }),
    );
    const res = await invoke({ user_id: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      issues: [{ iid: 1 }, { iid: 2 }],
      total: 2,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/issues",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          project_id: undefined,
          state: "opened",
          labels: undefined,
          milestone: undefined,
          author: undefined,
          assignee: undefined,
          limit: 100,
        }),
      },
    );
  });

  it("forwards explicit filters and honors NEXT_PUBLIC_API_BASE_URL", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:3131";
    mockFetch.mockResolvedValue(okResponse({ issues: [] }));
    await invoke({
      user_id: "u",
      project_id: "p",
      state: "closed",
      labels: "bug",
      milestone: "v1",
      author: "octocat",
      assignee: "reviewer",
      limit: 10,
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:3131/api/integrations/gitlab/issues",
    );
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      state: "closed",
      labels: "bug",
      milestone: "v1",
      author: "octocat",
      assignee: "reviewer",
      limit: 10,
    });
  });

  it("defaults to an empty issue list when the backend returns none", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, issues: [], total: 0 });
  });

  it("mirrors the backend error and status when the fetch fails", async () => {
    mockFetch.mockResolvedValue(failingResponse(401, { error: "token expired" }));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ ok: false, error: "token expired" });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(502, {}));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to fetch GitLab issues",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("network unreachable"));
    const res = await invoke({ user_id: "u" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
