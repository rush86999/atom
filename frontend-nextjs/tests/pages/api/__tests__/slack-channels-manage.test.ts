const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/slack/channels/manage";

describe("pages/api/integrations/slack/channels/manage", () => {
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

  it.each(["join", "leave", "archive", "unarchive"])(
    "performs the '%s' channel action and returns the backend payload",
    async (action) => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ok: true, action }),
      });
      const res = await invoke("POST", { channelId: "C123", action });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ ok: true, action });
      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toContain(`/api/slack/channels/C123/${action}`);
      expect(init.method).toBe("POST");
      expect(JSON.parse(init.body)).toEqual({ user_id: "current" });
    },
  );

  it("returns 400 when channelId is missing", async () => {
    const res = await invoke("POST", { action: "join" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "channelId and action are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when action is missing", async () => {
    const res = await invoke("POST", { channelId: "C123" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "channelId and action are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 for an unknown action", async () => {
    const res = await invoke("POST", { channelId: "C123", action: "rename" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "action must be one of: join, leave, archive, unarchive",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 with the backend payload when the action fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ error: "method_not_supported_for_token_type" }),
    });
    const res = await invoke("POST", { channelId: "C123", action: "archive" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "method_not_supported_for_token_type",
    });
  });

  it("returns 500 when the backend request throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { channelId: "C123", action: "join" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Failed to perform channel action",
    });
  });

  it("rejects non-POST methods with 405 and an Allow header", async () => {
    const res = await invoke("DELETE");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getData()).toBe("Method DELETE Not Allowed");
    expect(res.getHeader("Allow")).toEqual(["POST"]);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
