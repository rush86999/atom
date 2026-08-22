const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";

import zendeskAnalytics from "@/pages/api/zendesk/analytics";
import zendeskUsers from "@/pages/api/zendesk/users";

type Handler = (req: any, res: any) => void | Promise<void>;

// [suiteName, backendPath, errorLabel, failureMessage, handler]
// Both routes forward req.method to the backend and only send a body for
// non-GET requests.
const routes: Array<[string, string, string, string, Handler]> = [
  [
    "pages/api/zendesk/analytics",
    "/api/zendesk/analytics",
    "Zendesk analytics API error:",
    "Failed to fetch Zendesk analytics",
    zendeskAnalytics,
  ],
  [
    "pages/api/zendesk/users",
    "/api/zendesk/users",
    "Zendesk users API error:",
    "Failed to fetch Zendesk users",
    zendeskUsers,
  ],
];

const backendResponse = (status: number, data: any): any => ({
  ok: status < 400,
  status,
  json: async () => data,
});

describe.each(routes)(
  "%s",
  (_suite, backendPath, errorLabel, failureMessage, handler) => {
    beforeEach(() => {
      jest.clearAllMocks();
      delete process.env.PYTHON_API_SERVICE_BASE_URL;
      (global as any).fetch = mockFetch;
      jest.spyOn(console, "error").mockImplementation(() => {});
    });

    const invoke = async (method: string, body?: any) => {
      const { req, res } = createMocks({ method, body }) as any;
      await handler(req, res);
      return res;
    };

    it("forwards GET requests without a body", async () => {
      mockFetch.mockResolvedValue(
        backendResponse(200, { items: [{ id: "u-1" }] }),
      );
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ items: [{ id: "u-1" }] });
      expect(mockFetch).toHaveBeenCalledWith(
        `http://127.0.0.1:8000${backendPath}`,
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
          body: undefined,
        },
      );
    });

    it("forwards POST requests with a JSON body", async () => {
      mockFetch.mockResolvedValue(backendResponse(201, { created: true }));
      const res = await invoke("POST", { page: 3, role: "agent" });
      expect(res._getStatusCode()).toBe(201);
      expect(res._getJSONData()).toEqual({ created: true });
      expect(mockFetch).toHaveBeenCalledWith(
        `http://127.0.0.1:8000${backendPath}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ page: 3, role: "agent" }),
        },
      );
    });

    it("honours PYTHON_API_SERVICE_BASE_URL when set", async () => {
      process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend.test";
      mockFetch.mockResolvedValue(backendResponse(200, {}));
      await invoke("GET");
      expect(mockFetch.mock.calls[0][0]).toBe(`http://backend.test${backendPath}`);
    });

    it("passes backend errors straight through with their status", async () => {
      mockFetch.mockResolvedValue(
        backendResponse(502, { error: "Bad gateway" }),
      );
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(502);
      expect(res._getJSONData()).toEqual({ error: "Bad gateway" });
    });

    it("returns 500 with the error message when fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("connection reset"));
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: failureMessage,
        message: "connection reset",
      });
      expect(console.error).toHaveBeenCalledWith(errorLabel, expect.any(Error));
    });

    it("returns 500 with Unknown error when a non-Error is thrown", async () => {
      mockFetch.mockRejectedValue("boom");
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: failureMessage,
        message: "Unknown error",
      });
    });
  },
);
