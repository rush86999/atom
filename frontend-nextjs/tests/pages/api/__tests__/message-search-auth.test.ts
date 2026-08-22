const mockHandleMessage = jest.fn();
jest.mock("@/project/functions/atom-agent/src/handler", () => ({
  handleMessage: mockHandleMessage,
  HandleMessageResponse: {},
}));
jest.mock("@/pages/api/agent/handler", () => ({
  handleMessage: mockHandleMessage,
  HandleMessageResponse: {},
}));
const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));

import { createMocks } from "node-mocks-http";
import messageHandler from "@/pages/api/atom/message";
import accountsHandler from "@/pages/api/auth/accounts";
import searchHandler from "@/pages/api/search/[...path]";
import lancedbHandler from "@/pages/api/lancedb-search/[...path]";
import desktopProxy from "@/pages/api/agent/desktop-proxy";

const mockFetch = jest.fn();
const httpResponse = (ok: boolean, status: number, data: any, statusText = ""): any => ({
  ok,
  status,
  statusText,
  json: async () => data,
  text: async () => (typeof data === "string" ? data : JSON.stringify(data)),
});

describe("pages/api/atom/message", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockHandleMessage.mockResolvedValue({ text: "hi", conversationId: "c1" });
    jest.spyOn(console, "error").mockImplementation(() => {});
    jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("rejects non-POST with 405 and Allow header", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await messageHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getHeaders().allow).toEqual(["POST"]);
  });

  it("returns 400 when the message is missing", async () => {
    const { req, res } = createMocks({ method: "POST", body: { userId: "u1" } }) as any;
    await messageHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ text: "", error: "Missing message in request body" });
    expect(mockHandleMessage).not.toHaveBeenCalled();
  });

  it("returns 400 when the userId is missing", async () => {
    const { req, res } = createMocks({ method: "POST", body: { message: "hello" } }) as any;
    await messageHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ text: "", error: "Missing userId in request body" });
    expect(mockHandleMessage).not.toHaveBeenCalled();
  });

  it("calls handleMessage with options and returns the response", async () => {
    const { req, res } = createMocks({
      method: "POST",
      body: { message: "hello", userId: "u1", conversationId: "c1", intentName: "GREET", entities: { a: 1 } },
    }) as any;
    await messageHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ text: "hi", conversationId: "c1" });
    expect(mockHandleMessage).toHaveBeenCalledWith(
      "text",
      "hello",
      "u1",
      expect.objectContaining({ userId: "u1", conversationId: "c1", intentName: "GREET", entities: { a: 1 } }),
    );
  });

  it("omits options that are absent from the body", async () => {
    const { req, res } = createMocks({ method: "POST", body: { message: "hi", userId: "u1" } }) as any;
    await messageHandler(req, res);
    expect(mockHandleMessage).toHaveBeenCalledWith("text", "hi", "u1", { userId: "u1" });
  });

  it("returns 500 with the error message when handleMessage throws", async () => {
    mockHandleMessage.mockRejectedValue(new Error("agent crashed"));
    const { req, res } = createMocks({ method: "POST", body: { message: "hi", userId: "u1" } }) as any;
    await messageHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ text: "", error: "agent crashed" });
  });

  it("returns a fallback error when the rejection has no message", async () => {
    mockHandleMessage.mockRejectedValue({ name: "E" });
    const { req, res } = createMocks({ method: "POST", body: { message: "hi", userId: "u1" } }) as any;
    await messageHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      text: "",
      error: "Internal Server Error from Atom agent",
    });
  });
});

describe("pages/api/auth/accounts", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("returns 401 without an Authorization header", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await accountsHandler(req, res);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "Unauthorized - no token provided" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns transformed account data for a valid token", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {
      id: "u1",
      email: "a@b.c",
      name: "Alice",
      email_verified: true,
      image: "https://img/1",
      created_at: "2026-01-01",
    }));
    const { req, res } = createMocks({ method: "GET", headers: { authorization: "Bearer tok" } }) as any;
    await accountsHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.user).toEqual({
      email: "a@b.c",
      name: "",
      email_verified: true,
      image: "https://img/1",
      created_at: "2026-01-01",
    });
    expect(body.accounts).toEqual([
      {
        id: "u1",
        provider: "credentials",
        provider_account_id: "a@b.c",
        created_at: "2026-01-01",
        expires_at: null,
      },
    ]);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/me",
      { headers: { Authorization: "Bearer tok", "Content-Type": "application/json" } },
    );
  });

  it("derives the name from first/last name when name is absent", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {
      first_name: "Jane",
      last_name: "Doe",
    }));
    const { req, res } = createMocks({ method: "GET", headers: { authorization: "Bearer tok" } }) as any;
    await accountsHandler(req, res);
    expect(res._getJSONData().user.name).toBe("Jane Doe");
    expect(res._getJSONData().user.email).toBe("");
  });

  it("falls back to email for name, id, and timestamps", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { email: "x@y.z" }));
    const { req, res } = createMocks({ method: "GET", headers: { authorization: "Bearer tok" } }) as any;
    await accountsHandler(req, res);
    const body = res._getJSONData();
    expect(body.user.name).toBe("x@y.z");
    expect(body.user.email_verified).toBeNull();
    expect(body.user.image).toBeNull();
    expect(body.accounts[0].id).toBe("credentials-account");
  });

  it("mirrors backend auth errors", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 403, "forbidden"));
    const { req, res } = createMocks({ method: "GET", headers: { authorization: "Bearer tok" } }) as any;
    await accountsHandler(req, res);
    expect(res._getStatusCode()).toBe(403);
    expect(res._getJSONData()).toEqual({ error: "Backend auth error: 403" });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", headers: { authorization: "Bearer tok" } }) as any;
    await accountsHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to fetch account information" });
  });

  it("returns 400 for DELETE (unlinking unsupported)", async () => {
    const { req, res } = createMocks({ method: "DELETE", headers: { authorization: "Bearer tok" } }) as any;
    await accountsHandler(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Cannot remove the only authentication method." });
  });

  it("rejects other methods with 405", async () => {
    const { req, res } = createMocks({ method: "PUT", headers: { authorization: "Bearer tok" } }) as any;
    await accountsHandler(req, res);
    expect(res._getStatusCode()).toBe(405);
  });
});

describe("pages/api/search/[...path]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("joins the path segments and forwards GET", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { results: [] }));
    const { req, res } = createMocks({
      method: "GET",
      query: { path: ["documents", "42"] },
    }) as any;
    await searchHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ results: [] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/search/documents/42",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        body: undefined,
      },
    );
  });

  it("forwards the authorization header when present", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({
      method: "GET",
      query: { path: ["q"] },
      headers: { authorization: "Bearer tok" },
    }) as any;
    await searchHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/search/q",
      expect.objectContaining({
        headers: { "Content-Type": "application/json", Authorization: "Bearer tok" },
      }),
    );
  });

  it("sends a body for POST and mirrors status", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 201, { created: true }));
    const body = { query: "x" };
    const { req, res } = createMocks({ method: "POST", query: { path: ["documents"] }, body }) as any;
    await searchHandler(req, res);
    expect(res._getStatusCode()).toBe(201);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/search/documents",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  });

  it("returns backend error payload for failures", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 503, "no", "Service Unavailable"));
    const { req, res } = createMocks({ method: "GET", query: { path: "a" } }) as any;
    await searchHandler(req, res);
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Backend API error: Service Unavailable",
    });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: { path: "a" } }) as any;
    await searchHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Failed to connect to search backend",
    });
  });

  it("handles a missing path", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await searchHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/search/");
  });
});

describe("pages/api/lancedb-search/[...path]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("appends non-path query params to the URL", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { hits: [] }));
    const { req, res } = createMocks({
      method: "GET",
      query: { path: ["collections", "docs"], q: "hello", limit: "5" },
    }) as any;
    await lancedbHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/lancedb-search/collections/docs?q=hello&limit=5",
      expect.anything(),
    );
  });

  it("appends repeated array params", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({
      method: "GET",
      query: { path: ["s"], tag: ["a", "b"] },
    }) as any;
    await lancedbHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/lancedb-search/s?tag=a&tag=b");
  });

  it("omits the query string when there are no params", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, {}));
    const { req, res } = createMocks({ method: "GET", query: { path: ["s"] } }) as any;
    await lancedbHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/lancedb-search/s");
  });

  it("sends a body for POST and returns the data", async () => {
    mockFetch.mockResolvedValue(httpResponse(true, 200, { done: true }));
    const body = { vector: [1] };
    const { req, res } = createMocks({ method: "POST", query: { path: ["q"] }, body }) as any;
    await lancedbHandler(req, res);
    expect(res._getJSONData()).toEqual({ done: true });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/lancedb-search/q",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  });

  it("returns backend error payload for failures", async () => {
    mockFetch.mockResolvedValue(httpResponse(false, 502, "no", "Bad Gateway"));
    const { req, res } = createMocks({ method: "GET", query: { path: "a" } }) as any;
    await lancedbHandler(req, res);
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Backend API error: Bad Gateway",
    });
  });

  it("returns 500 when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: { path: "a" } }) as any;
    await lancedbHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
  });
});

describe("pages/api/agent/desktop-proxy", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue({ user: { id: "u1" } });
    mockHandleMessage.mockResolvedValue({ text: "ok" });
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("returns 401 without a session", async () => {
    mockGetServerSession.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "POST", body: { message: "m" } }) as any;
    await desktopProxy(req, res);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 400 when the message is missing", async () => {
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await desktopProxy(req, res);
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ message: "Message is required" });
  });

  it("forwards the message and settings to the handler", async () => {
    const { req, res } = createMocks({
      method: "POST",
      body: { message: "hello", settings: { voice: true } },
    }) as any;
    await desktopProxy(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ text: "ok" });
    expect(mockHandleMessage).toHaveBeenCalledWith("hello", { voice: true });
  });

  it("returns 500 when the handler throws", async () => {
    mockHandleMessage.mockRejectedValue(new Error("crash"));
    const { req, res } = createMocks({ method: "POST", body: { message: "m" } }) as any;
    await desktopProxy(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Failed to process message via desktop proxy",
    });
  });

  it("rejects non-POST with 405", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await desktopProxy(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getHeaders().allow).toEqual(["POST"]);
  });
});
