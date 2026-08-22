const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import notionStartHandler from "@/pages/api/notion/start";
import pocketStartHandler from "@/pages/api/pocket/oauth/start";
import teamsStartHandler from "@/pages/api/teams/start";

const okResponse = (data: any): any => ({
  ok: true,
  status: 200,
  json: async () => data,
});

const failingResponse = (status: number, data: any): any => ({
  ok: false,
  status,
  json: async () => data,
});

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.POCKET_CONSUMER_KEY;
  delete process.env.POCKET_REDIRECT_URI;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.POCKET_CONSUMER_KEY;
  delete process.env.POCKET_REDIRECT_URI;
});

// notion/start and teams/start share the same "authorize URL" shape against a
// hardcoded backend host.
const runAuthorizeSuite = (
  describeName: string,
  handler: any,
  backendPath: string,
  failureMessage: string,
) => {
  describe(describeName, () => {
    const invoke = async (query: any = { user_id: "user-1" }, method = "GET") => {
      const { req, res } = createMocks({ method, query }) as any;
      await handler(req, res);
      return res;
    };

    it("rejects non-GET methods with 405", async () => {
      const res = await invoke({ user_id: "user-1" }, "POST");
      expect(res._getStatusCode()).toBe(405);
      expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("returns 400 when user_id is missing", async () => {
      const res = await invoke({});
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({
        error: "user_id parameter is required",
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("fetches the authorization URL from the backend", async () => {
      mockFetch.mockResolvedValue(
        okResponse({
          auth_url: "https://provider.example/oauth/authorize?client_id=x",
          user_id: "user-1",
          csrf_token: "csrf-1",
        }),
      );
      const res = await invoke();
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({
        success: true,
        auth_url: "https://provider.example/oauth/authorize?client_id=x",
        user_id: "user-1",
        csrf_token: "csrf-1",
      });
      expect(mockFetch).toHaveBeenCalledWith(
        `http://127.0.0.1:8000${backendPath}?user_id=user-1`,
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    it("mirrors the backend error and status when the fetch fails", async () => {
      mockFetch.mockResolvedValue(failingResponse(503, { error: "provider down" }));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(503);
      expect(res._getJSONData()).toEqual({ error: "provider down" });
    });

    it("uses the default error message when the backend omits one", async () => {
      mockFetch.mockResolvedValue(failingResponse(500, {}));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({ error: failureMessage });
    });

    it("returns 500 with the error message when the fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("connection refused"));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: "Internal server error",
        message: "connection refused",
      });
      expect(console.error).toHaveBeenCalled();
    });

    it("reports Unknown error occurred for non-Error rejections", async () => {
      mockFetch.mockRejectedValue("boom");
      const res = await invoke();
      expect(res._getJSONData()).toEqual({
        error: "Internal server error",
        message: "Unknown error occurred",
      });
    });
  });
};

runAuthorizeSuite(
  "pages/api/notion/start",
  notionStartHandler,
  "/api/auth/notion/authorize",
  "Failed to start Notion OAuth",
);

runAuthorizeSuite(
  "pages/api/teams/start",
  teamsStartHandler,
  "/api/auth/teams/authorize",
  "Failed to start Teams OAuth",
);

describe("pages/api/pocket/oauth/start", () => {
  const invoke = async (method = "GET") => {
    const { req, res } = createMocks({ method }) as any;
    await pocketStartHandler(req, res);
    return res;
  };

  it("returns 500 when Pocket env vars are not configured", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Pocket environment variables not configured.",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 500 when only one of the env vars is configured", async () => {
    process.env.POCKET_CONSUMER_KEY = "consumer-key";
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("requests a Pocket code and redirects to the authorize URL", async () => {
    process.env.POCKET_CONSUMER_KEY = "consumer-key";
    process.env.POCKET_REDIRECT_URI = "http://localhost:3000/api/pocket/callback";
    mockFetch.mockResolvedValue(okResponse({ code: "request-token" }));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://getpocket.com/auth/authorize?request_token=request-token&redirect_uri=" +
        encodeURIComponent("http://localhost:3000/api/pocket/callback"),
    );
    expect(mockFetch).toHaveBeenCalledWith("https://getpocket.com/v3/oauth/request", {
      method: "POST",
      headers: {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Accept": "application/json",
      },
      body: JSON.stringify({
        consumer_key: "consumer-key",
        redirect_uri: "http://localhost:3000/api/pocket/callback",
      }),
    });
  });

  it("returns 500 when Pocket rejects the request token", async () => {
    process.env.POCKET_CONSUMER_KEY = "consumer-key";
    process.env.POCKET_REDIRECT_URI = "http://localhost:3000/api/pocket/callback";
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({}),
      text: async () => "invalid consumer key",
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Failed to start Pocket authentication",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 500 when the fetch to Pocket rejects", async () => {
    process.env.POCKET_CONSUMER_KEY = "consumer-key";
    process.env.POCKET_REDIRECT_URI = "http://localhost:3000/api/pocket/callback";
    mockFetch.mockRejectedValue(new Error("network gone"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Failed to start Pocket authentication",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
