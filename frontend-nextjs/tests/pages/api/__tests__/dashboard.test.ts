const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/dashboard";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/dashboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetServerSession.mockResolvedValue(mockSession);
  });

  const invoke = async (session: any = mockSession) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 401 when unauthenticated", async () => {
    const res = await invoke(null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 401 when the session has no user", async () => {
    const res = await invoke({ expires: "soon" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns the aggregated mock dashboard data with computed stats", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.calendar).toHaveLength(3);
    expect(body.tasks).toHaveLength(4);
    expect(body.messages).toHaveLength(4);
    // All mock events are in the future, one task is overdue and not
    // completed, two messages are unread, and one task is completed.
    expect(body.stats).toEqual({
      upcomingEvents: 3,
      overdueTasks: 1,
      unreadMessages: 2,
      completedTasks: 1,
    });
    expect(body.calendar[0]).toMatchObject({
      id: "1",
      title: "Team Standup Meeting",
      status: "confirmed",
    });
    expect(body.messages.map((m: any) => m.platform)).toEqual([
      "email",
      "slack",
      "teams",
      "discord",
    ]);
    expect(mockGetServerSession).toHaveBeenCalledTimes(1);
  });
});
