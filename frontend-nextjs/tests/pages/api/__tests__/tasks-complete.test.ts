const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

jest.mock("@/pages/api/auth/[...nextauth]", () => ({
  authOptions: { providers: [] },
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/tasks/[id]/complete";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/tasks/[id]/complete", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetServerSession.mockResolvedValue(mockSession);
  });

  const invoke = async (
    method: any = "POST",
    query: any = { id: "task-1" },
    session: any = mockSession,
  ) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("PUT", { id: "task-1" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ message: "Method not allowed" });
    expect(mockGetServerSession).not.toHaveBeenCalled();
  });

  it("returns 401 when unauthenticated", async () => {
    const res = await invoke("POST", { id: "task-1" }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 401 when the session has no user", async () => {
    const res = await invoke("POST", { id: "task-1" }, { expires: "soon" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 400 when the task id is missing", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ message: "Task ID is required" });
  });

  it("completes the task for the session user", async () => {
    const res = await invoke("POST", { id: "task-7" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      message: "Task marked as completed",
      taskId: "task-7",
    });
    expect(console.log).toHaveBeenCalledWith(
      "User user-1 completed task task-7",
    );
  });

  it("returns 500 when the simulated update throws", async () => {
    (console.log as jest.Mock).mockImplementation(() => {
      throw new Error("db offline");
    });
    const res = await invoke("POST", { id: "task-3" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Internal server error" });
    expect(console.error).toHaveBeenCalledWith(
      "Error completing task:",
      expect.any(Error),
    );
  });
});
