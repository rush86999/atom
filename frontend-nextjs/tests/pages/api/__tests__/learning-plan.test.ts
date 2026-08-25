const mockGetServerSession = jest.fn();

jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/projects/learning-plan";

const mockFetch = jest.fn();
const mockSession = {
  user: { id: "user-1", email: "user@example.com" },
};

function backendJson(body: any, ok = true, status = 200): any {
  return { ok, status, json: async () => body };
}

describe("pages/api/projects/learning-plan", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "POST", body: any = {}, session: any = mockSession) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405 and an Allow header", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res.getHeader("Allow")).toEqual(["POST"]);
  });

  it("returns 401 without a session", async () => {
    const res = await invoke("POST", { topic: "Rust" }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 400 when the topic is missing, empty, or whitespace", async () => {
    for (const body of [{}, { topic: "" }, { topic: "   " }, { topic: 42 }]) {
      const res = await invoke("POST", body);
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData().message).toBe("Topic is required");
    }
  });

  it("returns 400 for an invalid skill level", async () => {
    const res = await invoke("POST", { topic: "Rust", current_skill_level: "expert" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toContain("Invalid skill level");
  });

  it("returns 400 for an invalid time commitment", async () => {
    const res = await invoke("POST", { topic: "Rust", time_commitment: "all-day" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toContain("Invalid time commitment");
  });

  it("returns 400 when the duration is outside 1-52 weeks", async () => {
    for (const duration_weeks of [0, 53]) {
      const res = await invoke("POST", { topic: "Rust", duration_weeks });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData().message).toBe(
        "Duration must be between 1 and 52 weeks",
      );
    }
  });

  it("forwards a minimal request with defaults and maps the success payload", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        plan_id: "plan-1",
        topic: "Rust",
        current_skill_level: "beginner",
        target_skill_level: "intermediate",
        duration_weeks: 4,
        modules: [{ week: 1, title: "Ownership" }],
        milestones: ["Borrow checker"],
        assessment_criteria: ["Compiles"],
        created_at: "2026-08-01T00:00:00.000Z",
      }),
    );
    const res = await invoke("POST", { topic: "  Rust  " });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.plan_id).toBe("plan-1");
    expect(body.topic).toBe("Rust");
    expect(body.modules).toHaveLength(1);
    expect(body.milestones).toEqual(["Borrow checker"]);
    expect(body.assessment_criteria).toEqual(["Compiles"]);
    expect(body.message).toBe("Learning plan generated successfully");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/learning/plans",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "X-User-ID": "user-1",
        }),
      }),
    );
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      topic: "Rust",
      current_skill_level: "beginner",
      learning_goals: [],
      time_commitment: "medium",
      duration_weeks: 4,
      preferred_format: ["articles", "videos", "exercises"],
    });
  });

  it("forwards explicit preferences and the Notion database id", async () => {
    mockFetch.mockResolvedValue(backendJson({ plan_id: "plan-2", topic: "Rust", current_skill_level: "advanced", target_skill_level: "expert", duration_weeks: 12, modules: [], milestones: [], assessment_criteria: [] }));
    const res = await invoke("POST", {
      topic: "Rust",
      current_skill_level: "advanced",
      learning_goals: ["Build a compiler"],
      time_commitment: "high",
      duration_weeks: 12,
      preferred_format: ["videos"],
      notionDatabaseId: "db-9",
    });
    expect(res._getStatusCode()).toBe(200);
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      topic: "Rust",
      current_skill_level: "advanced",
      learning_goals: ["Build a compiler"],
      time_commitment: "high",
      duration_weeks: 12,
      preferred_format: ["videos"],
      notion_database_id: "db-9",
    });
  });

  it("omits the X-User-ID header when the session user has no id or email", async () => {
    mockFetch.mockResolvedValue(
      backendJson({ plan_id: "p", topic: "Rust", modules: [], milestones: [], assessment_criteria: [] }),
    );
    const res = await invoke("POST", { topic: "Rust" }, { user: {} });
    expect(res._getStatusCode()).toBe(200);
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["X-User-ID"]).toBeUndefined();
  });

  it("maps a backend 400 into a client 400 with detail", async () => {
    mockFetch.mockResolvedValue(backendJson({ detail: "Topic unsupported" }, false, 400));
    const res = await invoke("POST", { topic: "Rust" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe("Topic unsupported");
  });

  it("returns 500 when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { topic: "Rust" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Failed to generate learning plan",
      errors: ["ECONNREFUSED"],
    });
  });
});
