import { createMocks } from "node-mocks-http";
import analyticsHandler from "@/pages/api/integrations/figma/analytics";
import filesHandler from "@/pages/api/integrations/figma/files";
import profileHandler from "@/pages/api/integrations/figma/profile";

const mockFetch = jest.fn();
const httpResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/integrations/figma/analytics", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("forwards POST body to the backend and returns data", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { ok: true }));
    const body = { fileKey: "abc" };
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await analyticsHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/figma/analytics",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    );
  });

  it("mirrors backend failure as 400", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 401, { detail: "no" }));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await analyticsHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ detail: "no" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await analyticsHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ success: false, error: "Endpoint failed" });
  });

  it("rejects non-POST with 405 and Allow header", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await analyticsHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getHeaders().allow).toEqual(["POST"]);
  });
});

describe("pages/api/integrations/figma/files", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("forwards POST body to the backend and returns data", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { nodes: [] }));
    const body = { fileKey: "abc" };
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await filesHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ nodes: [] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/figma/files",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    );
  });

  it("mirrors backend failure as 400", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 500, { detail: "boom" }));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await filesHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ detail: "boom" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue("nope");
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await filesHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ success: false, error: "Endpoint failed" });
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "PUT" }) as any;
    await filesHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getHeaders().allow).toEqual(["POST"]);
  });
});

describe("pages/api/integrations/figma/profile", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("forwards GET to the backend and returns data", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { handle: "designer" }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await profileHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ handle: "designer" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/figma/user",
      { method: "GET", headers: { "Content-Type": "application/json" } },
    );
  });

  it("mirrors backend failure as 400", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 403, { detail: "forbidden" }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await profileHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ detail: "forbidden" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await profileHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ success: false, error: "Endpoint failed" });
  });

  it("rejects non-GET with 405 and Allow header", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await profileHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getHeaders().allow).toEqual(["GET"]);
  });
});
