const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/slack/search/files";

function backendResponse(ok: boolean, data: any, status = ok ? 200 : 400): any {
  return { ok, status, json: async () => data };
}

describe("pages/api/integrations/slack/search/files", () => {
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
    const res = await invoke("GET", { query: "report" });
    expect(res._getStatusCode()).toBe(405);
    expect(res.getHeader("Allow")).toEqual(["POST"]);
    expect(res._getData()).toBe("Method GET Not Allowed");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the query is missing", async () => {
    const res = await invoke("POST", { count: 10 });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "query is required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("searches files and returns the backend payload", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(true, { ok: true, files: [{ id: "F1", name: "a.pdf" }] }),
    );
    const res = await invoke("POST", { query: "report", count: 5, sort: "timestamp_asc" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      files: [{ id: "F1", name: "a.pdf" }],
    });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/slack/search/files");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({
      user_id: "current",
      query: "report",
      count: 5,
      sort: "timestamp_asc",
    });
  });

  it("applies default count and sort when omitted", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { ok: true, files: [] }));
    await invoke("POST", { query: "slides" });
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      user_id: "current",
      query: "slides",
      count: 50,
      sort: "timestamp_desc",
    });
  });

  it("returns 400 with the backend payload when the search fails", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(false, { ok: false, error: "search_disabled" }, 400),
    );
    const res = await invoke("POST", { query: "report" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ ok: false, error: "search_disabled" });
  });

  it("returns 500 when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { query: "report" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Failed to search files",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Error searching files:",
      expect.any(Error),
    );
  });
});
