const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/slack/channels/create";

function backendResponse(ok: boolean, data: any, status = ok ? 200 : 400): any {
  return { ok, status, json: async () => data };
}

describe("pages/api/integrations/slack/channels/create", () => {
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
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res.getHeader("Allow")).toEqual(["POST"]);
    expect(res._getData()).toBe("Method GET Not Allowed");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the name is missing", async () => {
    const res = await invoke("POST", { purpose: "no name" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "name is required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("creates the channel and returns 201 with the backend payload", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(true, { ok: true, channel: { id: "C123", name: "proj" } }, 201),
    );
    const res = await invoke("POST", {
      name: "proj",
      isPrivate: true,
      purpose: "project chat",
    });
    expect(res._getStatusCode()).toBe(201);
    expect(res._getJSONData()).toEqual({
      ok: true,
      channel: { id: "C123", name: "proj" },
    });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/slack/channels");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({
      user_id: "current",
      name: "proj",
      is_private: true,
      purpose: "project chat",
    });
  });

  it("applies defaults for isPrivate and purpose when omitted", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { ok: true }, 201));
    await invoke("POST", { name: "general" });
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      user_id: "current",
      name: "general",
      is_private: false,
      purpose: "",
    });
  });

  it("returns 400 with the backend payload when creation fails", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(false, { ok: false, error: "name_taken" }, 400),
    );
    const res = await invoke("POST", { name: "proj" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ ok: false, error: "name_taken" });
  });

  it("returns 500 when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { name: "proj" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Failed to create channel",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Error creating channel:",
      expect.any(Error),
    );
  });
});
