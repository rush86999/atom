const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/slack/messages/reactions";

describe("pages/api/integrations/slack/messages/reactions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method: any, body?: any) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  describe("POST", () => {
    it("returns 400 when required fields are missing", async () => {
      const res = await invoke("POST", { channelId: "C1" });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({
        success: false,
        error: "channelId, messageId, and reaction are required",
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("adds a reaction and returns the backend payload", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ok: true, reaction: "thumbsup" }),
      });
      const res = await invoke("POST", {
        channelId: "C1",
        messageId: "M1",
        reaction: "thumbsup",
      });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ ok: true, reaction: "thumbsup" });
      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toContain("/api/slack/messages/M1/reactions");
      expect(init.method).toBe("POST");
      expect(JSON.parse(init.body)).toEqual({
        user_id: "current",
        channel_id: "C1",
        reaction: "thumbsup",
      });
    });

    it("returns 400 with the backend payload when the add fails", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ error: "already_reacted" }),
      });
      const res = await invoke("POST", {
        channelId: "C1",
        messageId: "M1",
        reaction: "fire",
      });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({ error: "already_reacted" });
    });

    it("returns 500 when the add request throws", async () => {
      mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
      const res = await invoke("POST", {
        channelId: "C1",
        messageId: "M1",
        reaction: "fire",
      });
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        success: false,
        error: "Failed to add reaction",
      });
    });
  });

  describe("DELETE", () => {
    it("returns 400 when required fields are missing", async () => {
      const res = await invoke("DELETE", { messageId: "M1", reaction: "fire" });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({
        success: false,
        error: "channelId, messageId, and reaction are required",
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("removes a reaction and returns the backend payload", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ok: true, removed: true }),
      });
      const res = await invoke("DELETE", {
        channelId: "C1",
        messageId: "M1",
        reaction: "thumbsup",
      });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ ok: true, removed: true });
      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toContain("/api/slack/messages/M1/reactions/thumbsup");
      expect(init.method).toBe("DELETE");
      expect(JSON.parse(init.body)).toEqual({
        user_id: "current",
        channel_id: "C1",
      });
    });

    it("returns 400 with the backend payload when the removal fails", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ error: "reaction_not_found" }),
      });
      const res = await invoke("DELETE", {
        channelId: "C1",
        messageId: "M1",
        reaction: "fire",
      });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({ error: "reaction_not_found" });
    });

    it("returns 500 when the removal request throws", async () => {
      mockFetch.mockRejectedValue(new Error("socket hang up"));
      const res = await invoke("DELETE", {
        channelId: "C1",
        messageId: "M1",
        reaction: "fire",
      });
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        success: false,
        error: "Failed to remove reaction",
      });
    });
  });

  it("rejects unsupported methods with 405 and an Allow header", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getData()).toBe("Method GET Not Allowed");
    expect(res.getHeader("Allow")).toEqual(["POST", "DELETE"]);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
