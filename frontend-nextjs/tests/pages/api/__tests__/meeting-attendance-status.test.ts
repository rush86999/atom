const mockGetServerSession = jest.fn();
const mockPoolHolder: { pool: any; throwOnInit: boolean } = {
  pool: { connect: jest.fn() },
  throwOnInit: false,
};

jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));
jest.mock("pg", () => ({
  Pool: jest.fn(() => {
    if (mockPoolHolder.throwOnInit) {
      throw new Error("pg unavailable");
    }
    return mockPoolHolder.pool;
  }),
}));

const mockUseBackendApi = { value: false };
jest.mock("@/lib/api", () => ({
  get USE_BACKEND_API() {
    return mockUseBackendApi.value;
  },
  meetingAPI: { getMeetingAttendance: jest.fn() },
}));
jest.mock("@/lib/logger", () => ({
  __esModule: true,
  default: {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    fatal: jest.fn(),
    debug: jest.fn(),
  },
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/meeting_attendance_status/[taskId]";

const mockSession = {
  user: { id: "user-1", email: "user@example.com" },
  backendToken: "tok-123",
};

function makeClient(row: any = null) {
  return {
    query: jest.fn().mockResolvedValue({ rows: row ? [row] : [] }),
    release: jest.fn(),
  };
}

const dbRow = {
  task_id: "task-1",
  user_id: "user-1",
  platform: "zoom",
  meeting_identifier: "m-1",
  status_timestamp: "2026-08-01T10:00:00.000Z",
  current_status_message: "Attended",
  final_notion_page_url: "https://notion.so/page",
  error_details: null,
  created_at: "2026-08-01T09:00:00.000Z",
};

describe("pages/api/meeting_attendance_status/[taskId]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseBackendApi.value = false;
    mockGetServerSession.mockResolvedValue(mockSession);
    mockPoolHolder.throwOnInit = false;
    mockPoolHolder.pool.connect = jest.fn().mockResolvedValue(makeClient());
  });

  const invoke = async (
    method = "GET",
    query: any = { taskId: "task-1" },
    session: any = mockSession,
  ) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 401 when there is no session", async () => {
    const res = await invoke("GET", { taskId: "task-1" }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Unauthorized. Please log in." });
  });

  it("returns 405 with an Allow header for non-GET methods", async () => {
    const res = await invoke("POST", { taskId: "task-1" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method POST Not Allowed" });
    expect(res.getHeader("Allow")).toEqual(["GET"]);
  });

  it("returns 400 when taskId is missing", async () => {
    const res = await invoke("GET", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe(
      "Task ID is required and must be a string.",
    );
  });

  it("returns 400 when taskId is an array", async () => {
    const res = await invoke("GET", { taskId: ["a", "b"] });
    expect(res._getStatusCode()).toBe(400);
  });

  it("returns the status record from the DB for the authenticated user", async () => {
    mockPoolHolder.pool.connect.mockResolvedValue(makeClient(dbRow));
    const res = await invoke("GET", { taskId: "task-1" });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.task_id).toBe("task-1");
    expect(body.current_status_message).toBe("Attended");
    expect(body.final_notion_page_url).toBe("https://notion.so/page");
    expect(new Date(body.status_timestamp).toISOString()).toBe(body.status_timestamp);
    expect(new Date(body.created_at).toISOString()).toBe(body.created_at);
    const client = await mockPoolHolder.pool.connect.mock.results[0].value;
    expect(client.query).toHaveBeenCalledWith(
      "SELECT * FROM meeting_attendance_status WHERE task_id = $1 AND user_id = $2",
      ["task-1", "user-1"],
    );
    expect(client.release).toHaveBeenCalled();
  });

  it("returns 404 when no record exists for the user", async () => {
    mockPoolHolder.pool.connect.mockResolvedValue(makeClient(null));
    const res = await invoke("GET", { taskId: "task-1" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({
      error: "Task not found or not authorized.",
    });
  });

  it("returns 500 with details when the DB query fails", async () => {
    const client = makeClient();
    client.query.mockRejectedValue(new Error("relation does not exist"));
    mockPoolHolder.pool.connect.mockResolvedValue(client);
    const res = await invoke("GET", { taskId: "task-1" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal Server Error",
      details: "relation does not exist",
    });
    expect(client.release).toHaveBeenCalled();
  });

  it("returns 500 when the DB pool was never initialized", async () => {
    mockPoolHolder.throwOnInit = true;
    jest.resetModules();
    const freshHandler = (require("@/pages/api/meeting_attendance_status/[taskId]") as any)
      .default;
    mockPoolHolder.throwOnInit = false;
    mockGetServerSession.mockResolvedValue(mockSession);
    const { req, res } = createMocks({ method: "GET", query: { taskId: "task-1" } }) as any;
    await freshHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Database connection not configured.",
    });
  });

  describe("with USE_BACKEND_API enabled", () => {
    beforeEach(() => {
      mockUseBackendApi.value = true;
    });

    it("proxies to the backend API with the session token", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ task_id: "task-1", current_status_message: "Attended" }),
      });
      (global as any).fetch = mockFetch;
      const res = await invoke("GET", { taskId: "task-1" });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().current_status_message).toBe("Attended");
      expect(mockFetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/meetings/attendance/task-1",
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: "Bearer tok-123" }),
        }),
      );
    });

    it("returns 404 when the backend reports the task is missing", async () => {
      (global as any).fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
      const res = await invoke("GET", { taskId: "task-1" });
      expect(res._getStatusCode()).toBe(404);
      expect(res._getJSONData()).toEqual({
        error: "Task not found or not authorized.",
      });
    });

    it("falls back to the DB when the backend request fails", async () => {
      (global as any).fetch = jest
        .fn()
        .mockRejectedValue(new Error("ECONNREFUSED"));
      mockPoolHolder.pool.connect.mockResolvedValue(makeClient(dbRow));
      const res = await invoke("GET", { taskId: "task-1" });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().task_id).toBe("task-1");
    });

    it("falls back to the DB on backend server errors", async () => {
      (global as any).fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({}),
      });
      mockPoolHolder.pool.connect.mockResolvedValue(makeClient(dbRow));
      const res = await invoke("GET", { taskId: "task-1" });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().current_status_message).toBe("Attended");
    });
  });
});
