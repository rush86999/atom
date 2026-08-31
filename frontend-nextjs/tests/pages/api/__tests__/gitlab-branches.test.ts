const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/branches";

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

describe("pages/api/integrations/gitlab/branches", () => {
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

  it("fetches branches and forwards search/limit defaults", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        branches: [{ name: "main" }, { name: "feature/x" }],
        default_branch: "main",
      }),
    );
    const res = await invoke({ user_id: "user-1", project_id: "p-1", search: "feat" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      branches: [{ name: "main" }, { name: "feature/x" }],
      default_branch: "main",
      total: 2,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/branches",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          project_id: "p-1",
          search: "feat",
          limit: 100,
        }),
      },
    );
  });

  it("honors NEXT_PUBLIC_API_BASE_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:7000";
    mockFetch.mockResolvedValue(okResponse({ branches: [] }));
    await invoke({ user_id: "u", project_id: "p", limit: 5 });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:7000/api/integrations/gitlab/branches",
    );
  });

  it("defaults to an empty branch list when the backend returns none", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke({ user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      branches: [],
      default_branch: undefined,
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
    const res = await invoke({ user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to fetch GitLab branches",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("timeout"));
    const res = await invoke({ user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
