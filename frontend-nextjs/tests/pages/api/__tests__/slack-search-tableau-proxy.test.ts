const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";

import slackSearchMessages from "@/pages/api/integrations/slack/search/messages";
import tableauDataSources from "@/pages/api/integrations/tableau/data-sources";
import tableauProjects from "@/pages/api/integrations/tableau/projects";
import tableauProjectCreate from "@/pages/api/integrations/tableau/projects/create";
import tableauWorkbooks from "@/pages/api/integrations/tableau/workbooks";

type Handler = (req: any, res: any) => void | Promise<void>;

// [suiteName, backendPath, errorLabel, failureMessage, handler]
// These routes share an identical always-POST proxy shape: they forward the
// request body (forcing user_id to "current") to the Python backend and mirror
// the backend status/JSON back to the caller.
const routes: Array<[string, string, string, string, Handler]> = [
  [
    "pages/api/integrations/slack/search/messages",
    "/api/slack/search/messages",
    "Slack search API error:",
    "Failed to search Slack messages",
    slackSearchMessages,
  ],
  [
    "pages/api/integrations/tableau/data-sources",
    "/api/tableau/data-sources",
    "Tableau data sources API error:",
    "Failed to fetch Tableau data sources",
    tableauDataSources,
  ],
  [
    "pages/api/integrations/tableau/projects",
    "/api/tableau/projects",
    "Tableau projects API error:",
    "Failed to fetch Tableau projects",
    tableauProjects,
  ],
  [
    "pages/api/integrations/tableau/projects/create",
    "/api/tableau/projects/create",
    "Tableau project create error:",
    "Failed to create Tableau project",
    tableauProjectCreate,
  ],
  [
    "pages/api/integrations/tableau/workbooks",
    "/api/tableau/workbooks",
    "Tableau workbooks API error:",
    "Failed to fetch Tableau workbooks",
    tableauWorkbooks,
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

    const invoke = async (body?: any, method = "POST") => {
      const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
      await handler(req, res);
      return res;
    };

    it("proxies the request to the Python backend and mirrors the response", async () => {
      mockFetch.mockResolvedValue(
        backendResponse(200, { results: [{ id: "r-1" }] }),
      );
      const res = await invoke({ query: "deploy", limit: 10 });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ results: [{ id: "r-1" }] });
      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith(
        `http://127.0.0.1:8000${backendPath}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-user-id": "current",
          },
          body: JSON.stringify({ query: "deploy", limit: 10, user_id: "current" }),
        },
      );
    });

    it("honours PYTHON_API_SERVICE_BASE_URL when set", async () => {
      process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend.test";
      mockFetch.mockResolvedValue(backendResponse(200, { ok: true }));
      await invoke({ page: 2 });
      expect(mockFetch.mock.calls[0][0]).toBe(`http://backend.test${backendPath}`);
    });

    it("overrides any client-supplied user_id with 'current'", async () => {
      mockFetch.mockResolvedValue(backendResponse(200, {}));
      await invoke({ user_id: "attacker" });
      expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
        user_id: "current",
      });
    });

    it("passes backend errors straight through with their status", async () => {
      mockFetch.mockResolvedValue(
        backendResponse(401, { error: "Invalid credentials" }),
      );
      const res = await invoke({ user_id: "current" });
      expect(res._getStatusCode()).toBe(401);
      expect(res._getJSONData()).toEqual({ error: "Invalid credentials" });
    });

    it("returns 500 with the error message when fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("backend down"));
      const res = await invoke({});
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: failureMessage,
        message: "backend down",
      });
      expect(console.error).toHaveBeenCalledWith(errorLabel, expect.any(Error));
    });

    it("returns 500 with Unknown error when a non-Error is thrown", async () => {
      mockFetch.mockRejectedValue("boom");
      const res = await invoke({});
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: failureMessage,
        message: "Unknown error",
      });
    });
  },
);
