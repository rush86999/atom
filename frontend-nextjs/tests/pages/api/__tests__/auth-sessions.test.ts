const mockGetServerSession = jest.fn();
jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: mockGetServerSession,
}));

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

  it("returns 401 without a backend token instead of guessing authority", async () => {
    mockGetServerSession.mockResolvedValue({ user: { email: "user@example.com" } });
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(401);
    expect(mockFetch).not.toHaveBeenCalled();
    expect(res._getJSONData().error).toContain("Backend session unavailable");
  });

  describe("GET", () => {
    it("returns backend sessions with the bearer bound to the NextAuth session", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [{ id: "s1", is_current: true }],
      });
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ sessions: [{ id: "s1", is_current: true }] });
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/users/sessions"),
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({ Authorization: "Bearer bt-1" }),
        }),
      );
    });

    it.each([401, 403, 500])(
      "propagates backend status %s and never falls back to a direct DB read",
      async (status) => {
        mockFetch.mockResolvedValue({
          ok: false,
          status,
          json: async () => ({ detail: "backend refused" }),
        });
        const res = await invoke("GET");
        expect(res._getStatusCode()).toBe(status);
        expect(res._getJSONData().error).toBe("backend refused");
      },
    );

    it("returns 503 when the backend is unreachable", async () => {
      mockFetch.mockRejectedValue(new Error("backend down"));
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(503);
    });
  });

  describe("DELETE", () => {
    it("requires a session ID when revokeAll is not set", async () => {
      const res = await invoke("DELETE", {});
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData().error).toBe("Session ID is required");
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("revokes all sessions through the backend", async () => {
      mockFetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ revoked: 2 }) });
      const res = await invoke("DELETE", { revokeAll: true });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().message).toBe("All sessions revoked");
      expect(res._getJSONData().revoked).toBe(2);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/users/sessions"),
        expect.objectContaining({
          method: "DELETE",
          headers: expect.objectContaining({ Authorization: "Bearer bt-1" }),
        }),
      );
    });

    it("revokes a single session by its encoded id", async () => {
      mockFetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
      const res = await invoke("DELETE", { sessionId: "s/9" });
      expect(res._getStatusCode()).toBe(200);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/users/sessions/s%2F9"),
        expect.objectContaining({ method: "DELETE" }),
      );
    });

    it.each([401, 403, 409, 503])(
      "reports backend status %s instead of claiming success",
      async (status) => {
        mockFetch.mockResolvedValue({
          ok: false,
          status,
          json: async () => ({ message: "not revoked" }),
        });
        const res = await invoke("DELETE", { revokeAll: true });
        expect(res._getStatusCode()).toBe(status);
        expect(res._getJSONData().message).toBe("not revoked");
      },
    );

    it("returns 503 when the revocation request cannot be confirmed", async () => {
      mockFetch.mockRejectedValue(new Error("down"));
      const res = await invoke("DELETE", { revokeAll: true });
      expect(res._getStatusCode()).toBe(503);
      expect(res._getJSONData().error).toContain("could not be confirmed");
    });
  });

  describe("POST", () => {
    it("sends a bodyless heartbeat authenticated by the session bearer", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ tracked: true, registered: false, is_current: true }),
      });
      const res = await invoke("POST", { token: "client-supplied-must-be-ignored" });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({
        tracked: true,
        registered: false,
        is_current: true,
        message: "Session activity recorded",
      });
      const init = mockFetch.mock.calls[0][1];
      expect(init.body).toBeUndefined();
      expect(JSON.stringify(init)).not.toContain("client-supplied-must-be-ignored");
    });

    it("surfaces an untracked session honestly", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ tracked: false, registered: false, is_current: false, message: "not tracked" }),
      });
      const res = await invoke("POST", {});
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().tracked).toBe(false);
      expect(res._getJSONData().message).toBe("not tracked");
    });

    it("propagates a backend failure instead of reporting activity", async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500, json: async () => ({ detail: "nope" }) });
      const res = await invoke("POST", {});
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData().error).toBe("nope");
    });
  });

  it("returns 405 for unsupported methods", async () => {
    const res = await invoke("PUT");
    expect(res._getStatusCode()).toBe(405);
  });
});
