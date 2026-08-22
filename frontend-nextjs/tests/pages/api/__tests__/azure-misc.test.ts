const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import deployHandler from "@/pages/api/integrations/azure/app-services/deploy";
import costsHandler from "@/pages/api/integrations/azure/costs/analysis";
import storageFilesHandler from "@/pages/api/integrations/azure/storage/files";
import vmCreateHandler from "@/pages/api/integrations/azure/virtual-machines/create";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

// All four Azure routes share the same contract: POST proxy to the Python
// backend with the x-user-id header and user_id forced to "current".
type ProxyHandler = (req: any, res: any) => Promise<void>;

const proxyCases: Array<[string, ProxyHandler, string, string, string]> = [
  [
    "pages/api/integrations/azure/app-services/deploy",
    deployHandler,
    "http://127.0.0.1:8000/api/azure/app-services/deploy",
    "Failed to deploy Azure app service",
    "Azure app service deployment error:",
  ],
  [
    "pages/api/integrations/azure/costs/analysis",
    costsHandler,
    "http://127.0.0.1:8000/api/azure/costs/analysis",
    "Failed to fetch Azure cost analysis",
    "Azure cost analysis API error:",
  ],
  [
    "pages/api/integrations/azure/storage/files",
    storageFilesHandler,
    "http://127.0.0.1:8000/api/azure/storage/files",
    "Failed to fetch Azure storage files",
    "Azure storage files API error:",
  ],
  [
    "pages/api/integrations/azure/virtual-machines/create",
    vmCreateHandler,
    "http://127.0.0.1:8000/api/azure/virtual-machines/create",
    "Failed to create Azure virtual machine",
    "Azure VM creation error:",
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
        jsonResponse({ ok: true, result: "done" }, true, 200),
      );
      const res = await invoke({ resource_group: "rg-1", user_id: "ignored" });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ ok: true, result: "done" });
      expect(mockFetch).toHaveBeenCalledWith(backendPath, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
        body: JSON.stringify({
          resource_group: "rg-1",
          user_id: "current",
        }),
      });
    });

    it("honours PYTHON_API_SERVICE_BASE_URL and mirrors backend errors", async () => {
      process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
      mockFetch.mockResolvedValue(
        jsonResponse({ error: "subscription not found" }, false, 404),
      );
      const res = await invoke({ subscription_id: "sub" });
      expect(res._getStatusCode()).toBe(404);
      expect(res._getJSONData()).toEqual({ error: "subscription not found" });
      expect(mockFetch.mock.calls[0][0]).toBe(backendPath.replace("http://127.0.0.1:8000", "http://backend:5058"));
    });

    it("returns 500 when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("azure blew up"));
      const res = await invoke({});
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: failureError,
        message: "azure blew up",
      });
      expect(console.error).toHaveBeenCalledWith(
        logPrefix,
        expect.any(Error),
      );
    });
  });
});
