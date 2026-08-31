const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import quickbooksIntegrationsHealthHandler from "@/pages/api/integrations/quickbooks/health";
import quickbooksHealthHandler from "@/pages/api/quickbooks/health";
import zendeskHealthHandler from "@/pages/api/integrations/zendesk/health";
import rootHealthHandler from "@/pages/api/health";
import notionHealthHandler from "@/pages/api/integrations/notion/health";
import stripeHealthHandler from "@/pages/api/integrations/stripe/health";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

const resetEnv = () => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
};

// Shared contract for the simple "backend status" health routes: they call one
// GET status endpoint and merge the backend payload into
// { status: "healthy", backend: "connected", ...data } on success.
type StatusHealthHandler = (req: any, res: any) => Promise<void>;

const statusHealthCases: Array<[string, StatusHealthHandler, string]> = [
  [
    "pages/api/integrations/quickbooks/health",
    quickbooksIntegrationsHealthHandler,
    "http://127.0.0.1:8000/api/quickbooks/status",
  ],
  [
    "pages/api/quickbooks/health",
    quickbooksHealthHandler,
    "http://127.0.0.1:8000/api/quickbooks/health",
  ],
  [
    "pages/api/integrations/zendesk/health",
    zendeskHealthHandler,
    "http://127.0.0.1:8000/api/zendesk/status",
  ],
];

statusHealthCases.forEach(([label, handler, backendPath]) => {
  describe(label, () => {
    beforeEach(() => {
      jest.clearAllMocks();
      resetEnv();
      (global as any).fetch = mockFetch;
      jest.spyOn(console, "error").mockImplementation(() => {});
    });

    afterEach(resetEnv);

    const invoke = async () => {
      const { req, res } = createMocks({ method: "GET" }) as any;
      await handler(req, res);
      return res;
    };

    it("merges the backend payload into a healthy response", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ company_id: "cid", last_sync: "today" }, true),
      );
      const res = await invoke();
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({
        status: "healthy",
        backend: "connected",
        company_id: "cid",
        last_sync: "today",
      });
      expect(mockFetch).toHaveBeenCalledWith(backendPath, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
    });

    it("returns 503 when the backend responds with an error status", async () => {
      mockFetch.mockResolvedValue(jsonResponse({}, false, 500));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(503);
      expect(res._getJSONData().status).toBe("unhealthy");
      expect(res._getJSONData().error).toContain("not responding");
    });

    it("returns 503 when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("service gone"));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(503);
      expect(res._getJSONData().status).toBe("unhealthy");
      expect(console.error).toHaveBeenCalled();
    });
  });
});

describe("pages/api/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "GET", res?: any) => {
    const mocks = createMocks({ method: method as RequestMethod }) as any;
    await rootHealthHandler(mocks.req, res ?? mocks.res);
    return mocks.res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("reports frontend health details", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.service).toBe("atom-frontend");
    expect(body.version).toBe("1.0.0");
    expect(body.features).toEqual({
      byok: true,
      workflowAutomation: true,
      serviceIntegrations: true,
      voiceCommands: true,
      realTimeUpdates: true,
    });
    expect(body.dependencies).toEqual({
      backend: "http://127.0.0.1:8000",
      oauth: "http://127.0.0.1:8000",
    });
    expect(typeof body.uptime).toBe("number");
    expect(body.timestamp).toBeDefined();
  });

  it("returns 500 when serializing the health payload fails", async () => {
    // Simulate a response write failure for the success payload only, so the
    // catch branch of this synchronous handler is exercised.
    const failingRes: any = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn((data: any) => {
        if (data?.status === "healthy") {
          throw new Error("write failed");
        }
        return undefined;
      }),
    };
    await invoke("GET", failingRes);
    expect(failingRes.status).toHaveBeenCalledWith(500);
    expect(failingRes.json).toHaveBeenCalledWith(
      expect.objectContaining({ status: "unhealthy", error: "Internal server error" }),
    );
    expect(console.error).toHaveBeenCalled();
  });
});

// Shared contract for the demo-safe health routes (Notion, Stripe): a healthy
// payload is always returned, with backend data when available.
const demoHealthCases: Array<[string, StatusHealthHandler, string, string]> = [
  [
    "pages/api/integrations/notion/health",
    notionHealthHandler,
    "http://127.0.0.1:8000/api/notion/status",
    "Notion",
  ],
  [
    "pages/api/integrations/stripe/health",
    stripeHealthHandler,
    "http://127.0.0.1:8000/api/stripe/health",
    "Stripe",
  ],
];

demoHealthCases.forEach(([label, handler, backendPath, service]) => {
  describe(label, () => {
    beforeEach(() => {
      jest.clearAllMocks();
      resetEnv();
      (global as any).fetch = mockFetch;
      jest.spyOn(console, "error").mockImplementation(() => {});
    });

    afterEach(resetEnv);

    const invoke = async () => {
      const { req, res } = createMocks({ method: "GET" }) as any;
      await handler(req, res);
      return res;
    };

    it("wraps the backend payload in a healthy response", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ connected: true, details: "fine" }, true),
      );
      const res = await invoke();
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({
        status: "healthy",
        connected: true,
        service,
        backend_data: { connected: true, details: "fine" },
      });
      expect(mockFetch).toHaveBeenCalledWith(backendPath, expect.anything());
    });

    it("falls back to a healthy response when the backend responds not-ok", async () => {
      mockFetch.mockResolvedValue(jsonResponse({}, false, 500));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(200);
      const body = res._getJSONData();
      expect(body.status).toBe("healthy");
      expect(body.connected).toBe(true);
      expect(body.service).toBe(service);
      expect(body.timestamp).toBeDefined();
    });

    it("falls back to a healthy response when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("network gone"));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData().status).toBe("healthy");
      expect(console.error).toHaveBeenCalled();
    });
  });
});
