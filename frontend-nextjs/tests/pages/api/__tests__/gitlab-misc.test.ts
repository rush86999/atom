const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import projectHandler from "@/pages/api/integrations/gitlab/project";
import statusHandler from "@/pages/api/integrations/gitlab/status";
import triggerPipelineHandler from "@/pages/api/integrations/gitlab/trigger-pipeline";

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

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
});

const invoke = async (
  handler: any,
  body?: any,
  method = "POST",
): Promise<any> => {
  const { req, res } = createMocks({ method, body }) as any;
  await handler(req, res);
  return res;
};

describe("pages/api/integrations/gitlab/project", () => {
  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(projectHandler, undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when user_id or project_id is missing", async () => {
    const noUser = await invoke(projectHandler, { project_id: "p1" });
    expect(noUser._getStatusCode()).toBe(400);
    expect(noUser._getJSONData()).toEqual({
      error: "User ID and Project ID are required",
    });

    const noProject = await invoke(projectHandler, { user_id: "u1" });
    expect(noProject._getStatusCode()).toBe(400);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("fetches project details with default include flags", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        project: { id: 7, name: "repo" },
        stats: { stars: 3 },
      }),
    );
    const res = await invoke(projectHandler, {
      user_id: "user-1",
      project_id: "proj-1",
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      project: { id: 7, name: "repo" },
      pipelines: [],
      issues: [],
      merge_requests: [],
      commits: [],
      branches: [],
      stats: { stars: 3 },
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/project",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          project_id: "proj-1",
          include_pipelines: true,
          include_issues: true,
          include_merge_requests: true,
          include_commits: false,
          include_branches: false,
          pipeline_limit: 10,
          issue_limit: 20,
          mr_limit: 20,
          commit_limit: 10,
          branch_limit: 50,
        }),
      },
    );
  });

  it("forwards explicit include flags and limits", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        project: { id: 7 },
        pipelines: [{ id: 1 }],
        issues: [{ iid: 2 }],
        merge_requests: [{ iid: 3 }],
        commits: [{ id: "c" }],
        branches: [{ name: "dev" }],
      }),
    );
    const res = await invoke(projectHandler, {
      user_id: "u",
      project_id: "p",
      include_pipelines: false,
      include_issues: false,
      include_merge_requests: false,
      include_commits: true,
      include_branches: true,
      pipeline_limit: 1,
      issue_limit: 2,
      mr_limit: 3,
      commit_limit: 4,
      branch_limit: 5,
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toMatchObject({
      commits: [{ id: "c" }],
      branches: [{ name: "dev" }],
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      include_pipelines: false,
      include_issues: false,
      include_merge_requests: false,
      include_commits: true,
      include_branches: true,
      pipeline_limit: 1,
      issue_limit: 2,
      mr_limit: 3,
      commit_limit: 4,
      branch_limit: 5,
    });
  });

  it("honours NEXT_PUBLIC_API_BASE_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:5151";
    mockFetch.mockResolvedValue(okResponse({ project: {} }));
    await invoke(projectHandler, { user_id: "u", project_id: "p" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5151/api/integrations/gitlab/project",
    );
  });

  it("mirrors the backend error and status when the fetch fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(401, { error: "Invalid GitLab token" }),
    );
    const res = await invoke(projectHandler, {
      user_id: "u",
      project_id: "p",
    });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Invalid GitLab token",
    });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(503, {}));
    const res = await invoke(projectHandler, {
      user_id: "u",
      project_id: "p",
    });
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to fetch project details",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("backend down"));
    const res = await invoke(projectHandler, {
      user_id: "u",
      project_id: "p",
    });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/gitlab/status", () => {
  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(statusHandler, undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when user_id is missing", async () => {
    const res = await invoke(statusHandler, {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "User ID is required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("reports the connection status from the backend", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        connected: true,
        user: { username: "alice" },
        token_status: "valid",
        last_check: "2026-08-14T00:00:00Z",
      }),
    );
    const res = await invoke(statusHandler, { user_id: "user-1" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      connected: true,
      user: { username: "alice" },
      token_status: "valid",
      last_check: "2026-08-14T00:00:00Z",
      success: true,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/status",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "user-1" }),
      },
    );
  });

  it("honours NEXT_PUBLIC_API_BASE_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:5151";
    mockFetch.mockResolvedValue(okResponse({ connected: false }));
    await invoke(statusHandler, { user_id: "u" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5151/api/integrations/gitlab/status",
    );
  });

  it("mirrors the backend error and status when the fetch fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(401, { error: "No GitLab token stored" }),
    );
    const res = await invoke(statusHandler, { user_id: "u" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "No GitLab token stored",
    });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(500, {}));
    const res = await invoke(statusHandler, { user_id: "u" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to check GitLab status",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("network gone"));
    const res = await invoke(statusHandler, { user_id: "u" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/gitlab/trigger-pipeline", () => {
  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(triggerPipelineHandler, undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when user_id, project_id, or ref is missing", async () => {
    for (const body of [
      { project_id: "p", ref: "main" },
      { user_id: "u", ref: "main" },
      { user_id: "u", project_id: "p" },
    ]) {
      const res = await invoke(triggerPipelineHandler, body);
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({
        error: "User ID, Project ID, and Ref are required",
      });
    }
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("triggers the pipeline and echoes the backend payload", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        pipeline: { id: 99, status: "pending", web_url: "https://gitlab.com/p/-/pipelines/99" },
      }),
    );
    const res = await invoke(triggerPipelineHandler, {
      user_id: "user-1",
      project_id: "proj-1",
      ref: "feature/x",
      variables: [{ key: "ENV", value: "staging" }],
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      pipeline: { id: 99, status: "pending", web_url: "https://gitlab.com/p/-/pipelines/99" },
      url: "https://gitlab.com/p/-/pipelines/99",
      status: "pending",
      message: "Pipeline triggered for project proj-1 on branch feature/x",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/trigger-pipeline",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          project_id: "proj-1",
          ref: "feature/x",
          variables: [{ key: "ENV", value: "staging" }],
        }),
      },
    );
  });

  it("defaults variables to an empty list when omitted", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ pipeline: { id: 1, status: "running", web_url: "u" } }),
    );
    await invoke(triggerPipelineHandler, {
      user_id: "u",
      project_id: "p",
      ref: "main",
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      ref: "main",
      variables: [],
    });
  });

  it("mirrors the backend error and status when the fetch fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(400, { error: "Ref not found" }),
    );
    const res = await invoke(triggerPipelineHandler, {
      user_id: "u",
      project_id: "p",
      ref: "main",
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ ok: false, error: "Ref not found" });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(502, {}));
    const res = await invoke(triggerPipelineHandler, {
      user_id: "u",
      project_id: "p",
      ref: "main",
    });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to trigger pipeline",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("timeout"));
    const res = await invoke(triggerPipelineHandler, {
      user_id: "u",
      project_id: "p",
      ref: "main",
    });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
