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
import handler from "@/pages/api/messages/[id]/read";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/messages/[id]/read", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetServerSession.mockResolvedValue(mockSession);
  });

  const invoke = async (
    method: any = "POST",
    query: any = { id: "msg-1" },
    session: any = mockSession,
  ) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET", { id: "msg-1" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ message: "Method not allowed" });
    expect(mockGetServerSession).not.toHaveBeenCalled();
  });

  it("returns 401 when unauthenticated", async () => {
    const res = await invoke("POST", { id: "msg-1" }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 401 when the session has no user", async () => {
    const res = await invoke("POST", { id: "msg-1" }, { expires: "soon" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 400 when the message id is missing", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ message: "Message ID is required" });
  });

  it("marks the message as read for the session user", async () => {
    const res = await invoke("POST", { id: "msg-42" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      message: "Message marked as read",
      messageId: "msg-42",
    });
    expect(console.log).toHaveBeenCalledWith(
      "User user-1 marked message msg-42 as read",
    );
  });

  it("returns 500 when the simulated update throws", async () => {
    (console.log as jest.Mock).mockImplementation(() => {
      throw new Error("storage failure");
    });
    const res = await invoke("POST", { id: "msg-9" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ message: "Internal server error" });
    expect(console.error).toHaveBeenCalledWith(
      "Error marking message as read:",
      expect.any(Error),
    );
  });
});
