const mockFetch = jest.fn();

import { createMocks, type RequestMethod } from "node-mocks-http";
import nextjsStatusHandler from "@/pages/api/auth/nextjs/status";
import zapierHandler from "@/pages/api/atom/integrations/zapier";
import reportsHandler from "@/pages/api/quickbooks/reports/[reportType]";
import gmailStatusHandler from "@/pages/api/integrations/gmail/status";
import gmailAuthorizeHandler from "@/pages/api/integrations/gmail/authorize";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

const resetEnv = () => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
};

describe("pages/api/auth/nextjs/status", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (method: RequestMethod = "GET") => {
    const { req, res } = createMocks({ method }) as any;
    await nextjsStatusHandler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("maps the connected backend payload", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(
        {
          connected: true,
          user: { email: "dev@example.com" },
          team_id: "team-1",
          last_sync: "2026-08-14T00:00:00Z",
          extra: "dropped",
        },
        true,
      ),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      connected: true,
      user: { email: "dev@example.com" },
      team_id: "team-1",
      last_sync: "2026-08-14T00:00:00Z",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/nextjs/status",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("honours NEXT_PUBLIC_API_BASE_URL", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:5058";
    mockFetch.mockResolvedValue(jsonResponse({ connected: true }, true));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5058/api/auth/nextjs/status",
    );
  });

  it("mirrors the backend status and error message when not ok", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ error: "token revoked" }, false, 401),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      connected: false,
      error: "token revoked",
    });
  });

  it("falls back to a generic error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 502));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData()).toEqual({
      connected: false,
      error: "Failed to check Next.js status",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("status endpoint down"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      connected: false,
      error: "Internal server error",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/atom/integrations/zapier", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method: RequestMethod = "POST", body?: any, res?: any) => {
    const mocks = createMocks({ method, body }) as any;
    await zapierHandler(mocks.req, res ?? mocks.res);
    return res ?? mocks.res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getData()).toBe("Method GET Not Allowed");
  });

  it("logs the webhook payload and acknowledges it", async () => {
    const res = await invoke("POST", { zap: "data", id: 42 });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ message: "Data received successfully." });
    expect(console.log).toHaveBeenCalledWith("Received data from Zapier:", {
      zap: "data",
      id: 42,
    });
  });

  it("returns 500 when handling the webhook payload fails", async () => {
    // Simulate a response write failure for the success payload only, so the
    // catch branch of this handler is exercised.
    const failingRes: any = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn((data: any) => {
        if (data?.message === "Data received successfully.") {
          throw new Error("write failed");
        }
        return undefined;
      }),
    };
    await invoke("POST", { zap: "data" }, failingRes);
    expect(failingRes.status).toHaveBeenCalledWith(500);
    expect(failingRes.json).toHaveBeenCalledWith({
      message: "Failed to process webhook.",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/quickbooks/reports/[reportType]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (query: any) => {
    const { req, res } = createMocks({ method: "GET", query }) as any;
    await reportsHandler(req, res);
    return res;
  };

  it("rejects requests without a report type", async () => {
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Report type is required",
      message:
        "Please specify a report type (profitandloss, balancesheet, cashflow)",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("rejects requests with a non-string report type", async () => {
    const res = await invoke({ reportType: ["profitandloss", "balancesheet"] });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Report type is required");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("fetches the requested report and mirrors the payload", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ ReportName: "ProfitAndLoss", rows: [] }, true, 200),
    );
    const res = await invoke({ reportType: "profitandloss" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ReportName: "ProfitAndLoss",
      rows: [],
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/quickbooks/reports/profitandloss",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL and mirrors backend errors", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
    mockFetch.mockResolvedValue(
      jsonResponse({ error: "not connected to quickbooks" }, false, 400),
    );
    const res = await invoke({ reportType: "balancesheet" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "not connected to quickbooks",
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5058/api/quickbooks/reports/balancesheet",
    );
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("quickbooks offline"));
    const res = await invoke({ reportType: "cashflow" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch QuickBooks report",
      message: "quickbooks offline",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/gmail/status", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (method: RequestMethod = "GET") => {
    const { req, res } = createMocks({ method }) as any;
    await gmailStatusHandler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("PUT");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("reports connected with the backend data when healthy", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ data: { unread_count: 3 } }, true),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.connected).toBe(true);
    expect(body.service).toBe("gmail");
    expect(body.status).toBe("healthy");
    expect(body.data).toEqual({ unread_count: 3 });
    expect(body.timestamp).toBeDefined();
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/gmail/status",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("defaults the data object when the backend omits it", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, true));
    const res = await invoke();
    expect(res._getJSONData().data).toEqual({});
  });

  it("reports disconnected when the backend responds not-ok", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 503));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.connected).toBe(false);
    expect(body.status).toBe("disconnected");
    expect(body.error).toBe("Gmail service not available");
  });

  it("reports an error status when the fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("gmail unreachable"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.connected).toBe(false);
    expect(body.status).toBe("error");
    expect(body.error).toBe("Failed to check Gmail status");
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/gmail/authorize", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (method: RequestMethod = "GET", res?: any) => {
    const mocks = createMocks({ method }) as any;
    await gmailAuthorizeHandler(mocks.req, res ?? mocks.res);
    return res ?? mocks.res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("redirects to the backend Google OAuth initiation endpoint", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "http://127.0.0.1:8000/api/auth/google/initiate",
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
    const res = await invoke();
    expect(res._getRedirectUrl()).toBe(
      "http://backend:5058/api/auth/google/initiate",
    );
  });

  it("returns 500 when the redirect fails", async () => {
    // Simulate a response failure while issuing the redirect so the catch
    // branch of this handler is exercised.
    const failingRes: any = {
      redirect: jest.fn(() => {
        throw new Error("redirect failed");
      }),
      status: jest.fn().mockReturnThis(),
      json: jest.fn(),
    };
    await invoke("GET", failingRes);
    expect(failingRes.status).toHaveBeenCalledWith(500);
    expect(failingRes.json).toHaveBeenCalledWith(
      expect.objectContaining({
        error: "Failed to initiate Gmail OAuth flow",
        service: "gmail",
      }),
    );
    expect(console.error).toHaveBeenCalled();
  });
});
