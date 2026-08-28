const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import cyclesHandler from "@/pages/api/integrations/linear/cycles";
import projectsHandler from "@/pages/api/integrations/linear/projects";
import teamsHandler from "@/pages/api/integrations/linear/teams";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

// All three Linear routes share the same contract: the request method is
// forwarded, a body is only sent for non-GET requests, and the backend status
// and payload are mirrored.
type MethodProxyHandler = (req: any, res: any) => Promise<void>;

const proxyCases: Array<[string, MethodProxyHandler, string, string]> = [
  [
    "pages/api/integrations/linear/cycles",
    cyclesHandler,
    "http://127.0.0.1:8000/api/integrations/linear/cycles",
    "Failed to fetch Linear cycles",
  ],
  [
    "pages/api/integrations/linear/projects",
    projectsHandler,
    "http://127.0.0.1:8000/api/integrations/linear/projects",
    "Failed to fetch Linear projects",
  ],
  [
    "pages/api/integrations/linear/teams",
    teamsHandler,
    "http://127.0.0.1:8000/api/integrations/linear/teams",
    "Failed to fetch Linear teams",
  ],
];

proxyCases.forEach(([label, handler, backendPath, failureError]) => {
  describe(label, () => {
    beforeEach(() => {
      jest.clearAllMocks();
      delete process.env.PYTHON_API_SERVICE_BASE_URL;
      (global as any).fetch = mockFetch;
      jest.spyOn(console, "error").mockImplementation(() => {});
    });

    afterEach(() => {
      delete process.env.PYTHON_API_SERVICE_BASE_URL;
    });

    const invoke = async (method: string, body?: any) => {
      const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
      await handler(req, res);
      return res;
    };

    it("forwards GET requests without a body", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ success: true, data: [{ id: "l1" }] }, true, 200),
      );
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ success: true, data: [{ id: "l1" }] });
      expect(mockFetch).toHaveBeenCalledWith(backendPath, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        body: undefined,
      });
    });

    it("forwards POST requests with the JSON body", async () => {
      mockFetch.mockResolvedValue(jsonResponse({ created: true }, true, 201));
      const res = await invoke("POST", { team_id: "T1", name: "cycle" });
      expect(res._getStatusCode()).toBe(201);
      expect(mockFetch.mock.calls[0][1]).toEqual({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team_id: "T1", name: "cycle" }),
      });
    });

    it("honours PYTHON_API_SERVICE_BASE_URL and mirrors backend errors", async () => {
      process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
      mockFetch.mockResolvedValue(
        jsonResponse({ error: "linear token missing" }, false, 401),
      );
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(401);
      expect(res._getJSONData()).toEqual({ error: "linear token missing" });
      expect(mockFetch.mock.calls[0][0]).toBe(
        backendPath.replace("http://127.0.0.1:8000", "http://backend:5058"),
      );
    });

    it("returns 500 when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("linear offline"));
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: failureError,
        message: "linear offline",
      });
      expect(console.error).toHaveBeenCalled();
    });
  });
});
