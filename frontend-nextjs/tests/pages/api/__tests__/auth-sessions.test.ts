const mockGetServerSession = jest.fn();
jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: mockGetServerSession,
}));

const mockQuery = jest.fn();
jest.mock("@/lib/db", () => ({ query: mockQuery }));

const apiFlag = { USE_BACKEND_API: false, userManagementAPI: {} };
jest.mock("@/lib/api", () => apiFlag);

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/auth/sessions";

const mockFetch = jest.fn();

const mockSession = {
  user: { id: "user-1", email: "user@example.com" },
  backendToken: "bt-1",
} as any;

describe("pages/api/auth/sessions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    apiFlag.USE_BACKEND_API = false;
    mockGetServerSession.mockResolvedValue(mockSession);
    (global as any).fetch = mockFetch;
  });

  const invoke = async (method: RequestMethod = "GET", body: any = {}, headers: any = {}) => {
    const { req, res } = createMocks({ method, body, headers }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 401 when unauthenticated", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData().error).toBe("Unauthorized");
  });

  it("returns 404 when the user is not in the DB", async () => {
    mockQuery.mockResolvedValueOnce({ rows: [] });
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData().error).toBe("User not found");
  });

  describe("GET", () => {
    it("returns backend sessions when the backend API is enabled", async () => {
      apiFlag.USE_BACKEND_API = true;
      mockQuery.mockResolvedValueOnce({ rows: [{ id: "u1" }] });
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => [{ id: "s1" }],
      });
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ sessions: [{ id: "s1" }] });
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/users/sessions"),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer bt-1",
          }),
        }),
      );
    });

    it("falls back to the DB when the backend fails", async () => {
      apiFlag.USE_BACKEND_API = true;
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockResolvedValueOnce({ rows: [{ id: "db-session-1", is_current: true }] });
      mockFetch.mockRejectedValue(new Error("backend down"));
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().sessions).toEqual([{ id: "db-session-1", is_current: true }]);
    });

    it("lists active sessions from the DB", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockResolvedValueOnce({ rows: [{ id: "s1", is_active: true }] });
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().sessions).toEqual([{ id: "s1", is_active: true }]);
      expect(mockQuery.mock.calls[1][0]).toContain("FROM user_sessions");
      expect(mockQuery.mock.calls[1][1]).toEqual(["u1", "bt-1"]);
    });

    it("returns 500 when the DB query fails", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockRejectedValueOnce(new Error("db down"));
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData().error).toBe("Internal server error");
    });
  });

  describe("DELETE", () => {
    it("revokes all sessions via the backend", async () => {
      apiFlag.USE_BACKEND_API = true;
      mockQuery.mockResolvedValueOnce({ rows: [{ id: "u1" }] });
      mockFetch.mockResolvedValue({ ok: true });
      const res = await invoke("DELETE", { revokeAll: true });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().message).toBe("All sessions revoked");
    });

    it("requires a session ID when revokeAll is not set", async () => {
      mockQuery.mockResolvedValueOnce({ rows: [{ id: "u1" }] });
      const res = await invoke("DELETE", {});
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData().error).toBe("Session ID is required");
    });

    it("revokes a single session via the backend", async () => {
      apiFlag.USE_BACKEND_API = true;
      mockQuery.mockResolvedValueOnce({ rows: [{ id: "u1" }] });
      mockFetch.mockResolvedValue({ ok: true });
      const res = await invoke("DELETE", { sessionId: "s-9" });
      expect(res._getStatusCode()).toBe(200);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/users/sessions/s-9"),
        expect.objectContaining({ method: "DELETE" }),
      );
    });

    it("falls back to DB revoke-all when the backend throws", async () => {
      apiFlag.USE_BACKEND_API = true;
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockResolvedValueOnce({ rows: [] });
      mockFetch.mockRejectedValue(new Error("down"));
      const res = await invoke("DELETE", { revokeAll: true });
      expect(res._getStatusCode()).toBe(200);
      expect(mockQuery.mock.calls[1][0]).toContain(
        "UPDATE user_sessions SET is_active = false",
      );
    });

    it("revokes all sessions in the DB", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockResolvedValueOnce({ rows: [] });
      const res = await invoke("DELETE", { revokeAll: true });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().message).toBe("All sessions revoked");
    });

    it("revokes a single session scoped to the user", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockResolvedValueOnce({ rows: [] });
      const res = await invoke("DELETE", { sessionId: "s-1" });
      expect(res._getStatusCode()).toBe(200);
      expect(mockQuery.mock.calls[1][1]).toEqual(["s-1", "u1"]);
    });

    it("returns 500 when the DB revoke fails", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockRejectedValueOnce(new Error("db down"));
      const res = await invoke("DELETE", { revokeAll: true });
      expect(res._getStatusCode()).toBe(500);
    });
  });

  describe("POST", () => {
    it("requires a token", async () => {
      mockQuery.mockResolvedValueOnce({ rows: [{ id: "u1" }] });
      const res = await invoke("POST", {});
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData().error).toBe("Token required");
    });

    it("records a session with parsed device/browser/os info", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockResolvedValueOnce({ rows: [] });
      const res = await invoke(
        "POST",
        { token: "sess-tok-1" },
        {
          "user-agent":
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
          "x-forwarded-for": "203.0.113.9",
        },
      );
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().message).toBe("Session recorded");
      const params = mockQuery.mock.calls[1][1];
      expect(params[0]).toBe("u1");
      expect(params[1]).toBe("sess-tok-1");
      expect(params[2]).toContain("iPhone");
      expect(params[3]).toBe("203.0.113.9");
    });

    it("uses the first IP when x-forwarded-for is an array", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockResolvedValueOnce({ rows: [] });
      const res = await invoke(
        "POST",
        { token: "t2" },
        { "x-forwarded-for": ["10.0.0.1", "10.0.0.2"] },
      );
      expect(res._getStatusCode()).toBe(200);
      expect(mockQuery.mock.calls[1][1][3]).toBe("10.0.0.1");
    });

    it("returns 500 when the DB insert fails", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "u1" }] })
        .mockRejectedValueOnce(new Error("db down"));
      const res = await invoke("POST", { token: "t3" });
      expect(res._getStatusCode()).toBe(500);
    });
  });

  it("returns 405 for unsupported methods", async () => {
    mockQuery.mockResolvedValueOnce({ rows: [{ id: "u1" }] });
    const res = await invoke("PUT");
    expect(res._getStatusCode()).toBe(405);
  });
});
