const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/create-merge-request";

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

describe("pages/api/integrations/gitlab/create-merge-request", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (body?: any, method: RequestMethod = "POST") => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  const validBody = {
    user_id: "user-1",
    project_id: "p-1",
    source_branch: "feature/x",
    target_branch: "main",
    title: "Add feature x",
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it.each([
    ["user_id", { ...validBody, user_id: undefined }],
    ["project_id", { ...validBody, project_id: undefined }],
    ["source_branch", { ...validBody, source_branch: undefined }],
    ["target_branch", { ...validBody, target_branch: undefined }],
    ["title", { ...validBody, title: undefined }],
  ])("returns 400 when %s is missing", async (_field, body) => {
    const res = await invoke(body);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error:
        "User ID, Project ID, Source Branch, Target Branch, and Title are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("creates a merge request and returns the url and message", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        merge_request: {
          id: 12,
          title: "Add feature x",
          web_url: "https://gitlab.com/p/-/merge_requests/12",
        },
      }),
    );
    const res = await invoke({
      ...validBody,
      description: "does the thing",
      assignee_ids: [5],
      reviewer_ids: [6],
      labels: ["feature"],
      milestone_id: 9,
      remove_source_branch: true,
      squash: true,
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      merge_request: {
        id: 12,
        title: "Add feature x",
        web_url: "https://gitlab.com/p/-/merge_requests/12",
      },
      url: "https://gitlab.com/p/-/merge_requests/12",
      message: "Merge request created: Add feature x",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/create-merge-request",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...validBody,
          description: "does the thing",
          assignee_ids: [5],
          reviewer_ids: [6],
          labels: ["feature"],
          milestone_id: 9,
          remove_source_branch: true,
          squash: true,
        }),
      },
    );
  });

  it("honors NEXT_PUBLIC_API_BASE_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:6000";
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke(validBody);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:6000/api/integrations/gitlab/create-merge-request",
    );
  });

  it("falls back to the submitted title when the backend omits the merge request", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke(validBody);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      merge_request: undefined,
      url: undefined,
      message: "Merge request created: Add feature x",
    });
  });

  it("mirrors the backend error and status when creation fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(409, { error: "Merge request already exists" }),
    );
    const res = await invoke(validBody);
    expect(res._getStatusCode()).toBe(409);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Merge request already exists",
    });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(500, {}));
    const res = await invoke(validBody);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to create merge request",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("tls error"));
    const res = await invoke(validBody);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
