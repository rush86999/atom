const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import authStartHandler from "@/pages/api/integrations/slack/auth/start";
import userInfoHandler from "@/pages/api/integrations/slack/user/info";
import callbackHandler from "@/pages/api/integrations/slack/callback";
import messagesHandler from "@/pages/api/integrations/slack/messages";
import channelsHandler from "@/pages/api/integrations/slack/channels";
import usersHandler from "@/pages/api/integrations/slack/users";
import sendHandler from "@/pages/api/integrations/slack/messages/send";
import oauthStartHandler from "@/pages/api/slack/oauth/start";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

const resetEnv = () => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  delete process.env.SLACK_CLIENT_ID;
  delete process.env.SLACK_REDIRECT_URI;
};

describe("pages/api/integrations/slack/auth/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await authStartHandler(req, res);
    return res;
  };

  it("redirects to the authorization URL returned by the backend", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ url: "https://slack.com/oauth/v2/authorize?state=abc" }, true),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://slack.com/oauth/v2/authorize?state=abc",
    );
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/auth/url",
      { headers: {} },
    );
  });

  it("returns 500 when the backend responds without a URL", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, true));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to get Slack authorization URL",
      message: "No authorization URL returned from backend",
    });
  });

  it("returns 500 when the backend responds with an error status", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 503));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Backend Slack service error",
      message: "Failed to contact Slack authentication service",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("slack backend down"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to start Slack OAuth flow",
      message: "slack backend down",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/slack/user/info", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (options: any) => {
    const { req, res } = createMocks(options) as any;
    await userInfoHandler(req, res);
    return res;
  };

  it("forwards GET requests without extra query parameters or a body", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ ok: true, user: { id: "U1" } }, true, 200),
    );
    const res = await invoke({ method: "GET", query: { id: "U1" } });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, user: { id: "U1" } });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/user/info",
      {
        method: "GET",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
        body: undefined,
      },
    );
  });

  it("appends remaining query parameters and forwards the body for POST", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
    mockFetch.mockResolvedValue(jsonResponse({ ok: false }, false, 404));
    const res = await invoke({
      method: "POST",
      query: { id: "U1", cursor: "cur-9", limit: "5" },
      body: { include_locale: true },
    });
    expect(res._getStatusCode()).toBe(404);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5058/api/slack/user/info?cursor=cur-9&limit=5",
    );
    expect(mockFetch.mock.calls[0][1]).toEqual({
      method: "POST",
      headers: { "Content-Type": "application/json", "x-user-id": "current" },
      body: JSON.stringify({ include_locale: true }),
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("timeout"));
    const res = await invoke({ method: "GET", query: {} });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Slack user info",
      message: "timeout",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/slack/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (query: any = { code: "code-1", state: "state-1" }) => {
    const { req, res } = createMocks({ method: "GET", query }) as any;
    await callbackHandler(req, res);
    return res;
  };

  it("exchanges the code and redirects to the success page", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ ok: true, access_token: "xoxb" }, true),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations/slack?success=true");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/callback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: "code-1",
          state: "state-1",
          user_id: "current",
        }),
      },
    );
  });

  it("returns 400 with the backend message on OAuth failure", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ message: "invalid code" }, false, 400),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Slack OAuth",
      message: "invalid code",
    });
  });

  it("falls back to a generic message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 500));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Slack OAuth",
      message: "Unknown OAuth error",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("oauth exploded"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Slack OAuth flow",
      message: "oauth exploded",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/slack/messages", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (body: any) => {
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await messagesHandler(req, res);
    return res;
  };

  it("fetches channel history with default limit and current user", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ ok: true, messages: [{ ts: "1" }] }, true, 200),
    );
    const res = await invoke({ channelId: "C123" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, messages: [{ ts: "1" }] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/conversations/history?channel=C123&limit=10&user_id=current",
      {
        method: "GET",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
      },
    );
  });

  it("honours explicit limits and user_id", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
    mockFetch.mockResolvedValue(jsonResponse({ ok: false }, false, 401));
    const res = await invoke({
      channelId: "C9",
      limit: 25,
      user_id: "user-42",
      extra: "ignored",
    });
    expect(res._getStatusCode()).toBe(401);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5058/api/slack/conversations/history?channel=C9&limit=25&user_id=user-42",
    );
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("history unavailable"));
    const res = await invoke({ channelId: "C123" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Slack messages",
      message: "history unavailable",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/slack/channels", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (options: any) => {
    const { req, res } = createMocks({ method: "GET", ...options }) as any;
    await channelsHandler(req, res);
    return res;
  };

  it("defaults the user id to current when none is supplied", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ ok: true, channels: [] }, true, 200),
    );
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, channels: [] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/channels?user_id=current",
      {
        method: "GET",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
      },
    );
  });

  it("prefers the query user_id over the body user_id", async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }, true, 200));
    await invoke({ query: { user_id: "from-query" }, body: { user_id: "from-body" } });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/slack/channels?user_id=from-query",
    );
  });

  it("uses the body user_id when the query has none", async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }, true, 200));
    await invoke({ body: { user_id: "from-body" } });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/slack/channels?user_id=from-body",
    );
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("no channels"));
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Slack channels",
      message: "no channels",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/slack/users", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (options: any) => {
    const { req, res } = createMocks({ method: "GET", ...options }) as any;
    await usersHandler(req, res);
    return res;
  };

  it("fetches the current user by default", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ ok: true, user: { name: "alice" } }, true, 200),
    );
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, user: { name: "alice" } });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/users/current",
      {
        method: "GET",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
      },
    );
  });

  it("uses the query user_id when provided", async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }, true, 200));
    await invoke({ query: { user_id: "U999" }, body: { user_id: "U111" } });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/slack/users/U999",
    );
  });

  it("uses the body user_id when the query has none", async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }, true, 200));
    await invoke({ body: { user_id: "U111" } });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/slack/users/U111",
    );
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("users endpoint down"));
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Slack users",
      message: "users endpoint down",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/slack/messages/send", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (body: any) => {
    const { req, res } = createMocks({ method: "POST", body }) as any;
    await sendHandler(req, res);
    return res;
  };

  it("posts the message with the current user id", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ ok: true, ts: "1690000000.000100" }, true, 200),
    );
    const res = await invoke({
      channel: "C1",
      text: "hello world",
      user_id: "should-be-overridden",
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ ok: true, ts: "1690000000.000100" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/slack/messages",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
        body: JSON.stringify({
          channel: "C1",
          text: "hello world",
          user_id: "current",
        }),
      },
    );
  });

  it("mirrors backend error statuses", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
    mockFetch.mockResolvedValue(jsonResponse({ ok: false, error: "channel_not_found" }, false, 404));
    const res = await invoke({ channel: "C404", text: "hi" });
    expect(res._getStatusCode()).toBe(404);
    expect(mockFetch.mock.calls[0][0]).toBe("http://backend:5058/api/slack/messages");
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("send failed"));
    const res = await invoke({ channel: "C1", text: "hi" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to send Slack message",
      message: "send failed",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/slack/oauth/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    oauthStartHandler(req, res);
    return res;
  };

  it("returns 500 when Slack environment variables are missing", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Slack environment variables not configured.",
    });
  });

  it("redirects to the Slack authorization URL when configured", async () => {
    process.env.SLACK_CLIENT_ID = "client-123";
    process.env.SLACK_REDIRECT_URI = "http://localhost:3000/api/slack/callback";
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://slack.com/oauth/v2/authorize?client_id=client-123&scope=chat:write,commands,users:read,users:read.email&redirect_uri=http://localhost:3000/api/slack/callback&state=some-random-state",
    );
  });
});
