const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/slack/messages/edit";

function backendResponse(ok: boolean, data: any, status = ok ? 200 : 400): any {
  return { ok, status, json: async () => data };
}

describe("pages/api/integrations/slack/messages/edit", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (method: any = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 with an Allow header for non-POST methods", async () => {
    const res = await invoke("PUT", { channelId: "C1", message: "hi" });
    expect(res._getStatusCode()).toBe(405);
    expect(res.getHeader("Allow")).toEqual(["POST"]);
    expect(res._getData()).toBe("Method PUT Not Allowed");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when channelId is missing", async () => {
    const res = await invoke("POST", { message: "updated text" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "channelId and message are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when message is missing", async () => {
    const res = await invoke("POST", { channelId: "C1" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "channelId and message are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("edits the message and returns the backend payload", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { ok: true, ts: "123.456" }));
    const res = await invoke("POST", { channelId: "C1", message: "new text" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, ts: "123.456" });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/slack/messages/edit");
    expect(init.method).toBe("PUT");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({
      user_id: "current",
      channel_id: "C1",
      text: "new text",
    });
  });

  it("returns 400 with the backend payload when the edit fails", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(false, { ok: false, error: "cant_edit_message" }, 400),
    );
    const res = await invoke("POST", { channelId: "C1", message: "x" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ ok: false, error: "cant_edit_message" });
  });

  it("returns 500 when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { channelId: "C1", message: "x" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Failed to edit message",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Error editing message:",
      expect.any(Error),
    );
  });
});
