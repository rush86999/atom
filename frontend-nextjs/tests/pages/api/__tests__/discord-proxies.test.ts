import { createMocks } from "node-mocks-http";
import healthHandler from "@/pages/api/integrations/discord/health";
import profileHandler from "@/pages/api/integrations/discord/profile";
import analyticsHandler from "@/pages/api/integrations/discord/analytics";
import channelsHandler from "@/pages/api/integrations/discord/channels";
import guildsHandler from "@/pages/api/integrations/discord/guilds";
import messagesHandler from "@/pages/api/integrations/discord/messages";

const mockFetch = jest.fn();

const httpResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/integrations/discord (GET proxies)", () => {
  const cases: Array<[string, any, string, string, string]> = [
    ["health", healthHandler, "GET", "/api/integrations/discord/health", "5059"],
    ["profile", profileHandler, "GET", "/api/discord/user", "5058"],
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it.each(cases)("%s forwards GET to the backend and returns data", async (name, handler, _method, endpoint, port) => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { success: true, user: name }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true, user: name });
    expect(mockFetch).toHaveBeenCalledWith(
      `http://127.0.0.1:8000${endpoint}`,
      { method: "GET", headers: { "Content-Type": "application/json" } },
    );
  });

  it.each(cases)("%s mirrors backend failure as 400", async (name, handler) => {
    mockFetch.mockResolvedValue(httpResponse(false, 502, { detail: "upstream" }));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ detail: "upstream" });
  });

  it.each(cases)("%s returns 500 when the backend fetch rejects", async (name, handler) => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ success: false, error: "Endpoint failed" });
  });

  it.each(cases)("%s rejects non-GET with 405 and Allow header", async (name, handler) => {
    for (const method of ["POST", "PUT"] as const) {
      const { req, res } = createMocks({ method }) as any;
      await handler(req, res);
      expect(res._getStatusCode()).toBe(405);
      expect(res._getHeaders().allow).toEqual(["GET"]);
      expect(mockFetch).not.toHaveBeenCalled();
    }
  });
});

describe("pages/api/integrations/discord (POST proxies)", () => {
  const cases: Array<[string, any, string]> = [
    ["analytics", analyticsHandler, "/api/integrations/discord/analytics"],
    ["channels", channelsHandler, "/api/integrations/discord/channels"],
    ["guilds", guildsHandler, "/api/integrations/discord/guilds"],
    ["messages", messagesHandler, "/api/integrations/discord/messages"],
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it.each(cases)("%s forwards POST body to the backend", async (name, handler, endpoint) => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { ok: true }));
    const body = { channelId: "c1", content: "hello" };
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledWith(
      `http://127.0.0.1:8000${endpoint}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  });

  it.each(cases)("%s mirrors backend failure as 400", async (name, handler) => {
    mockFetch.mockResolvedValue(httpResponse(false, 404, { detail: "missing" }));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ detail: "missing" });
  });

  it.each(cases)("%s returns 500 when the backend fetch rejects", async (name, handler) => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ success: false, error: "Endpoint failed" });
  });

  it.each(cases)("%s rejects non-POST with 405 and Allow header", async (name, handler) => {
    for (const method of ["GET", "DELETE"] as const) {
      const { req, res } = createMocks({ method }) as any;
      await handler(req, res);
      expect(res._getStatusCode()).toBe(405);
      expect(res._getHeaders().allow).toEqual(["POST"]);
    }
  });
});
