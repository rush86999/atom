import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/graphrag/[...path]";

const mockFetch = jest.fn();

const jsonResponse = (body: any, status = 200) => ({
  ok: status < 400,
  status,
  headers: {
    get: (name: string) =>
      name.toLowerCase() === "content-type" ? "application/json" : null,
  },
  json: async () => body,
  text: async () => JSON.stringify(body),
});

const htmlResponse = (status = 503) => ({
  ok: false,
  status,
  headers: {
    get: (name: string) => (name.toLowerCase() === "content-type" ? "text/html" : null),
  },
  json: async () => ({}),
  text: async () => "<html>Bad Gateway</html>",
});

describe("pages/api/graphrag/[...path]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.BACKEND_URL;
    delete process.env.NEXT_PUBLIC_API_URL;
    mockFetch.mockResolvedValue(jsonResponse({ success: true, result: "ok" }));
  });

  afterEach(() => {
    delete process.env.BACKEND_URL;
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (
    method = "GET",
    query: any = {},
    opts: { headers?: any; body?: any } = {},
  ) => {
    const { req, res } = createMocks({
      method,
      query,
      headers: opts.headers,
      body: opts.body,
    }) as any;
    await handler(req, res);
    return res;
  };

  it("proxies to the primary backend path and returns the JSON payload", async () => {
    const res = await invoke("GET", { path: ["health", "status"] });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true, result: "ok" });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/graphrag/api/graphrag/health/status",
    );
    expect(mockFetch.mock.calls[0][1].method).toBe("GET");
    expect(mockFetch.mock.calls[0][1].body).toBeUndefined();
  });

  it("falls back to the short backend path after a 404", async () => {
    mockFetch
      .mockResolvedValueOnce(jsonResponse({ error: "not found" }, 404))
      .mockResolvedValueOnce(jsonResponse({ success: true, source: "fallback" }));
    const res = await invoke("GET", { path: ["documents"] });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true, source: "fallback" });
    expect(mockFetch.mock.calls[1][0]).toBe(
      "http://127.0.0.1:8000/api/graphrag/documents",
    );
  });

  it("accepts a plain string path segment", async () => {
    await invoke("GET", { path: "health" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/graphrag/api/graphrag/health",
    );
  });

  it("handles a missing path segment", async () => {
    await invoke("GET", {});
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/graphrag/api/graphrag/",
    );
  });

  it("prefers BACKEND_URL over NEXT_PUBLIC_API_URL", async () => {
    process.env.BACKEND_URL = "http://graphrag-backend:9000";
    process.env.NEXT_PUBLIC_API_URL = "http://other:7000";
    jest.resetModules();
    const freshHandler = (await import("@/pages/api/graphrag/[...path]")).default;
    const { req, res } = createMocks({ method: "GET", query: { path: ["x"] } }) as any;
    await freshHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://graphrag-backend:9000/api/graphrag/api/graphrag/x",
    );
  });

  it("uses NEXT_PUBLIC_API_URL when BACKEND_URL is unset", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://other:7000";
    jest.resetModules();
    const freshHandler = (await import("@/pages/api/graphrag/[...path]")).default;
    const { req, res } = createMocks({ method: "GET", query: { path: ["x"] } }) as any;
    await freshHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://other:7000/api/graphrag/api/graphrag/x",
    );
  });

  it("appends query parameters, dropping path and undefined values", async () => {
    await invoke("GET", {
      path: ["search"],
      q: "atoms",
      tags: ["a", "b"],
      missing: undefined,
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/graphrag/api/graphrag/search?q=atoms&tags=a&tags=b",
    );
  });

  it("forwards method, body and auth headers for POST requests", async () => {
    await invoke(
      "POST",
      { path: ["query"] },
      {
        headers: {
          authorization: "Bearer tok",
          cookie: "session=abc",
        },
        body: { question: "what?" },
      },
    );
    const call = mockFetch.mock.calls[0];
    expect(call[0]).toBe("http://127.0.0.1:8000/api/graphrag/api/graphrag/query");
    expect(call[1].method).toBe("POST");
    expect(call[1].headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer tok",
      Cookie: "session=abc",
    });
    expect(JSON.parse(call[1].body)).toEqual({ question: "what?" });
  });

  it("sends no body for HEAD requests without one", async () => {
    await invoke("HEAD", { path: ["health"] });
    expect(mockFetch.mock.calls[0][1].body).toBeUndefined();
  });

  it("returns 502 with a preview when the backend replies non-JSON with 200", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "text/plain" },
      json: async () => ({}),
      text: async () => "plain text body",
    });
    const res = await invoke("GET", { path: ["x"] });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "GraphRAG backend returned a non-JSON response",
      status: 200,
      preview: "plain text body",
    });
  });

  it("passes through the upstream status for non-JSON error responses", async () => {
    mockFetch.mockResolvedValue(htmlResponse(503));
    const res = await invoke("GET", { path: ["x"] });
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toMatchObject({
      success: false,
      status: 503,
      preview: "<html>Bad Gateway</html>",
    });
  });

  it("passes through an error JSON status from the backend", async () => {
    mockFetch.mockResolvedValue(jsonResponse({ error: "bad request" }, 400));
    const res = await invoke("GET", { path: ["x"] });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "bad request" });
  });

  it("returns 502 when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("GET", { path: ["x"] });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Failed to connect to GraphRAG backend",
      message: "ECONNREFUSED",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("reports an unknown error message for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("just a string");
    const res = await invoke("GET", { path: ["x"] });
    expect(res._getJSONData().message).toBe("Unknown error");
  });
});
