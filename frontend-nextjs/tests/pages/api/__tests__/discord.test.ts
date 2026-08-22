const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import analyticsHandler from "@/pages/api/integrations/discord/analytics";
import channelsHandler from "@/pages/api/integrations/discord/channels";
import guildsHandler from "@/pages/api/integrations/discord/guilds";
import healthHandler from "@/pages/api/integrations/discord/health";
import messagesHandler from "@/pages/api/integrations/discord/messages";
import profileHandler from "@/pages/api/integrations/discord/profile";

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
});

// Every handler in this family proxies to a single fixed backend endpoint and
// maps non-ok backend responses to a 400. `allowedMethod` is the only method
// the handler accepts; anything else gets a 405 with an Allow header.
const runDiscordSuite = (
  describeName: string,
  handler: any,
  backendUrl: string,
  allowedMethod: "POST" | "GET",
  payload: any,
) => {
  describe(describeName, () => {
    const invoke = async (method = allowedMethod, body?: any) => {
      const { req, res } = createMocks({ method, body }) as any;
      await handler(req, res);
      return res;
    };

    it(`rejects non-${allowedMethod} methods with 405 and an Allow header`, async () => {
      const other = allowedMethod === "POST" ? "GET" : "POST";
      const res = await invoke(other);
      expect(res._getStatusCode()).toBe(405);
      expect(res.getHeader("Allow")).toEqual([allowedMethod]);
      expect(res._getData()).toBe(`Method ${other} Not Allowed`);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("returns the backend payload on success", async () => {
      mockFetch.mockResolvedValue(jsonResponse(true, 200, payload));
      const res = await invoke(allowedMethod, payload);
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual(payload);
      expect(mockFetch).toHaveBeenCalledWith(
        backendUrl,
        allowedMethod === "POST"
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            }
          : {
              method: "GET",
              headers: { "Content-Type": "application/json" },
            },
      );
    });

    it("maps non-ok backend responses to 400 with the payload", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse(false, 500, { error: "discord unavailable" }),
      );
      const res = await invoke();
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({ error: "discord unavailable" });
    });

    it("returns 500 when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("backend down"));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        success: false,
        error: "Endpoint failed",
      });
      expect(console.error).toHaveBeenCalled();
    });
  });
};

runDiscordSuite(
  "pages/api/integrations/discord/analytics",
  analyticsHandler,
  "http://127.0.0.1:8000/api/integrations/discord/analytics",
  "POST",
  { guild_id: "g1", messages_analyzed: 10 },
);

runDiscordSuite(
  "pages/api/integrations/discord/channels",
  channelsHandler,
  "http://127.0.0.1:8000/api/integrations/discord/channels",
  "POST",
  { channels: [{ id: "c1", name: "general" }] },
);

runDiscordSuite(
  "pages/api/integrations/discord/guilds",
  guildsHandler,
  "http://127.0.0.1:8000/api/integrations/discord/guilds",
  "POST",
  { guilds: [{ id: "g1", name: "Atom" }] },
);

runDiscordSuite(
  "pages/api/integrations/discord/health",
  healthHandler,
  "http://127.0.0.1:8000/api/integrations/discord/health",
  "GET",
  { status: "healthy" },
);

runDiscordSuite(
  "pages/api/integrations/discord/messages",
  messagesHandler,
  "http://127.0.0.1:8000/api/integrations/discord/messages",
  "POST",
  { messages: [{ id: "m1" }] },
);

runDiscordSuite(
  "pages/api/integrations/discord/profile",
  profileHandler,
  "http://127.0.0.1:8000/api/discord/user",
  "GET",
  { id: "u1", username: "atom-user" },
);

describe("pages/api/integrations/discord (shared env handling)", () => {
  it("honours PYTHON_API_SERVICE_BASE_URL for guilds", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5058";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    const { req, res } = createMocks({
      method: "POST",
      body: { guild_id: "g1" },
    }) as any;
    await guildsHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://python:5058/api/integrations/discord/guilds",
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL for profile", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5059";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    const { req, res } = createMocks({ method: "GET" }) as any;
    await profileHandler(req, res);
    expect(mockFetch.mock.calls[0][0]).toBe("http://python:5059/api/discord/user");
  });
});
