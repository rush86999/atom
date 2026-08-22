import { createMocks } from "node-mocks-http";
import filesHandler from "@/pages/api/integrations/slack/files";
import uploadHandler from "@/pages/api/integrations/slack/files/upload";

const mockFetch = jest.fn();
const httpResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/integrations/slack/files", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("lists files with query params forwarded", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { files: [] }));
    const { req, res } = createMocks({
      method: "GET",
      query: { channel: "C1", limit: "10" },
    }) as any;
    await filesHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ files: [] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/files?channel=C1&limit=10",
      {
        method: "GET",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
        body: undefined,
      },
    );
  });

  it("appends the file id to the URL when provided", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { file: { id: "F1" } }));
    const { req, res } = createMocks({
      method: "GET",
      query: { id: "F123" },
    }) as any;
    await filesHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/files/F123",
      expect.anything(),
    );
    expect(res._getJSONData()).toEqual({ file: { id: "F1" } });
  });

  it("sends the body for non-GET methods", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 201, { ok: true }));
    const body = { channel: "C1" };
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await filesHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/files",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
        body: JSON.stringify(body),
      },
    );
  });

  it("mirrors backend status", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 404, { detail: "missing" }));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await filesHandler(req, res);
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ detail: "missing" });
  });

  it("returns 500 with message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await filesHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Slack files",
      message: "down",
    });
  });

  it("falls back to Unknown error for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("x");
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await filesHandler(req, res);
    expect(res._getJSONData().message).toBe("Unknown error");
  });
});

describe("pages/api/integrations/slack/files/upload", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects uploads without a file with 400", async () => {
    const { req, res } = createMocks({
      method: "POST",
      body: { channels: [] },
    }) as any;
    await uploadHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ success: false, error: "file is required" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("uploads a file with channels, title and comment appended to FormData", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { ok: true, file: {} }));
    const file = new Blob(["data"], { type: "text/plain" });
    const { req, res } = createMocks({
      method: "POST",
      body: { channels: ["C1", "C2"], title: "Report", initialComment: "hi" },
    }) as any;
    req.files = { file };
    await uploadHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, file: {} });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/slack/files/upload");
    expect(opts.method).toBe("POST");
    const form = opts.body as FormData;
    expect(String(form.get("file"))).toBe("[object Blob]");
    expect(form.get("channels")).toBe("C1,C2");
    expect(form.get("title")).toBe("Report");
    expect(form.get("initial_comment")).toBe("hi");
  });

  it("omits empty channels and optional fields", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { ok: true }));
    const file = new Blob(["x"]);
    const { req, res } = createMocks({
      method: "POST",
      body: { channels: [], title: "", initialComment: "" },
    }) as any;
    req.files = { file };
    await uploadHandler(req, res);
    const form = (mockFetch.mock.calls[0][1] as any).body as FormData;
    expect(String(form.get("file"))).toBe("[object Blob]");
    expect(form.get("channels")).toBeNull();
    expect(form.get("title")).toBeNull();
    expect(form.get("initial_comment")).toBeNull();
  });

  it("mirrors backend failure as 400", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 415, { detail: "bad type" }));
    const file = new Blob(["x"]);
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    req.files = { file };
    await uploadHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ detail: "bad type" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const file = new Blob(["x"]);
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    req.files = { file };
    await uploadHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ success: false, error: "Failed to upload file" });
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await uploadHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getHeaders().allow).toEqual(["POST"]);
  });
});
