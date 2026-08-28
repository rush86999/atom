const mockGetServerSession = jest.fn();

jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/projects/health";

const mockFetch = jest.fn();
const mockSession = {
  user: { id: "user-1", email: "user@example.com" },
};

function backendJson(body: any, ok = true, status = 200): any {
  return { ok, status, json: async () => body };
}

describe("pages/api/projects/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "POST", body: any = {}, session: any = mockSession) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405 and an Allow header", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res.getHeader("Allow")).toEqual(["POST"]);
  });

  it("returns 401 without a session", async () => {
    const res = await invoke("POST", { github_owner: "o", github_repo: "r" }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("rejects time ranges outside 1-90 days", async () => {
    const res = await invoke("POST", {
      github_owner: "o",
      github_repo: "r",
      time_range_days: 0,
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe(
      "Time range must be between 1 and 90 days",
    );
  });

  it("rejects requests without any integration credentials", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toContain("At least one integration");
    expect(res._getJSONData().hint).toBeDefined();
  });

  it("requires both notion key and database id for Notion to count", async () => {
    const res = await invoke("POST", { notion_api_key: "sk-123" });
    expect(res._getStatusCode()).toBe(400);
  });

  it("forwards a GitHub check with defaults and maps the success payload", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        check_id: "chk-1",
        overall_score: 82,
        overall_status: "good",
        metrics: { velocity: 80, quality: 84 },
        recommendations: ["Ship faster"],
        checked_at: "2026-08-01T00:00:00.000Z",
        time_range_days: 7,
      }),
    );
    const res = await invoke("POST", {
      github_owner: "atom",
      github_repo: "atom",
    });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.check_id).toBe("chk-1");
    expect(body.overall_score).toBe(82);
    expect(body.overall_status).toBe("good");
    expect(body.metrics).toEqual({ velocity: 80, quality: 84 });
    expect(body.message).toBe("Project health check completed successfully");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/projects/health",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-User-ID": "user-1" }),
      }),
    );
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      time_range_days: 7,
      github_owner: "atom",
      github_repo: "atom",
    });
  });

  it("forwards Notion and Slack credentials plus an explicit time range", async () => {
    mockFetch.mockResolvedValue(backendJson({ overall_score: 60, overall_status: "warning", metrics: {}, recommendations: [] }));
    const res = await invoke("POST", {
      notion_api_key: "sk-1",
      notion_database_id: "db-1",
      slack_channel_id: "C123",
      time_range_days: 30,
    });
    expect(res._getStatusCode()).toBe(200);
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      time_range_days: 30,
      notion_api_key: "sk-1",
      notion_database_id: "db-1",
      slack_channel_id: "C123",
    });
  });

  it("omits the X-User-ID header when the session user has no id or email", async () => {
    mockFetch.mockResolvedValue(
      backendJson({ overall_score: 1, overall_status: "good", metrics: {}, recommendations: [] }),
    );
    const res = await invoke(
      "POST",
      { github_owner: "o", github_repo: "r" },
      { user: {} },
    );
    expect(res._getStatusCode()).toBe(200);
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["X-User-ID"]).toBeUndefined();
  });

  it("maps a backend 400 into a client 400 with detail", async () => {
    mockFetch.mockResolvedValue(
      backendJson({ detail: "Invalid integration" }, false, 400),
    );
    const res = await invoke("POST", { github_owner: "o", github_repo: "r" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe("Invalid integration");
  });

  it("returns 500 when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { github_owner: "o", github_repo: "r" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Failed to check project health",
      errors: ["ECONNREFUSED"],
    });
  });
});
