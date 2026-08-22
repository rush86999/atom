const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import tasksHandler from "@/pages/api/integrations/google-workspace/tasks";
import docsCreateHandler from "@/pages/api/integrations/google-workspace/docs/create";
import keepNotesHandler from "@/pages/api/integrations/google-workspace/keep/notes";
import tasksCreateHandler from "@/pages/api/integrations/google-workspace/tasks/create";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

// All four Google Workspace routes share the same contract: POST proxy to the
// Python backend with the x-user-id header and user_id forced to "current".
type ProxyHandler = (req: any, res: any) => Promise<void>;

const proxyCases: Array<[string, ProxyHandler, string, string, string]> = [
  [
    "pages/api/integrations/google-workspace/tasks",
    tasksHandler,
    "http://127.0.0.1:8000/api/google-workspace/tasks",
    "Failed to fetch Google Tasks",
    "Google Tasks API error:",
  ],
  [
    "pages/api/integrations/google-workspace/docs/create",
    docsCreateHandler,
    "http://127.0.0.1:8000/api/google-workspace/docs/create",
    "Failed to create Google Doc",
    "Google Docs create error:",
  ],
  [
    "pages/api/integrations/google-workspace/keep/notes",
    keepNotesHandler,
    "http://127.0.0.1:8000/api/google-workspace/keep/notes",
    "Failed to fetch Google Keep notes",
    "Google Keep API error:",
  ],
  [
    "pages/api/integrations/google-workspace/tasks/create",
    tasksCreateHandler,
    "http://127.0.0.1:8000/api/google-workspace/tasks/create",
    "Failed to create Google Task",
    "Google Tasks create error:",
  ],
];

proxyCases.forEach(([label, handler, backendPath, failureError, logPrefix]) => {
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

    const invoke = async (body: any) => {
      const { req, res } = createMocks({ method: "POST", body }) as any;
      await handler(req, res);
      return res;
    };

    it("proxies the body with the current user id and returns the payload", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ success: true, items: [] }, true, 200),
      );
      const res = await invoke({ title: "new item", user_id: "ignored" });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ success: true, items: [] });
      expect(mockFetch).toHaveBeenCalledWith(backendPath, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
        body: JSON.stringify({ title: "new item", user_id: "current" }),
      });
    });

    it("honours PYTHON_API_SERVICE_BASE_URL and mirrors backend errors", async () => {
      process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
      mockFetch.mockResolvedValue(
        jsonResponse({ error: "no google token" }, false, 401),
      );
      const res = await invoke({ title: "x" });
      expect(res._getStatusCode()).toBe(401);
      expect(res._getJSONData()).toEqual({ error: "no google token" });
      expect(mockFetch.mock.calls[0][0]).toBe(
        backendPath.replace("http://127.0.0.1:8000", "http://backend:5058"),
      );
    });

    it("returns 500 when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("workspace offline"));
      const res = await invoke({});
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: failureError,
        message: "workspace offline",
      });
      expect(console.error).toHaveBeenCalledWith(logPrefix, expect.any(Error));
    });
  });
});
