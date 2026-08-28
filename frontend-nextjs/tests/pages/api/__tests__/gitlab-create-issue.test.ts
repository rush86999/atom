const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/gitlab/create-issue";

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

describe("pages/api/integrations/gitlab/create-issue", () => {
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

  it.each([
    ["user_id", { project_id: "p-1", title: "Bug" }],
    ["project_id", { user_id: "u-1", title: "Bug" }],
    ["title", { user_id: "u-1", project_id: "p-1" }],
  ])("returns 400 when %s is missing", async (_field, body) => {
    const res = await invoke(body);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "User ID, Project ID, and Title are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("creates an issue and returns the url and message", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        issue: { id: 7, title: "Bug", web_url: "https://gitlab.com/p/-/issues/7" },
      }),
    );
    const res = await invoke({
      user_id: "user-1",
      project_id: "p-1",
      title: "Bug",
      description: "steps",
      labels: ["backend"],
      assignee_ids: [42],
      milestone_id: 3,
      weight: 2,
      confidential: true,
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      issue: { id: 7, title: "Bug", web_url: "https://gitlab.com/p/-/issues/7" },
      url: "https://gitlab.com/p/-/issues/7",
      message: "Issue created: Bug",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/gitlab/create-issue",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "user-1",
          project_id: "p-1",
          title: "Bug",
          description: "steps",
          labels: ["backend"],
          assignee_ids: [42],
          milestone_id: 3,
          weight: 2,
          confidential: true,
        }),
      },
    );
  });

  it("honors NEXT_PUBLIC_API_BASE_URL when configured", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:4242";
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke({ user_id: "u", project_id: "p", title: "T" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:4242/api/integrations/gitlab/create-issue",
    );
  });

  it("falls back to the submitted title when the backend omits the issue", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke({ user_id: "u", project_id: "p", title: "My title" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      issue: undefined,
      url: undefined,
      message: "Issue created: My title",
    });
  });

  it("mirrors the backend error and status when creation fails", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(400, { error: "Title is too short" }),
    );
    const res = await invoke({ user_id: "u", project_id: "p", title: "x" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Title is too short",
    });
  });

  it("uses the default error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(failingResponse(500, {}));
    const res = await invoke({ user_id: "u", project_id: "p", title: "T" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Failed to create issue",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("connection reset"));
    const res = await invoke({ user_id: "u", project_id: "p", title: "T" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      ok: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
