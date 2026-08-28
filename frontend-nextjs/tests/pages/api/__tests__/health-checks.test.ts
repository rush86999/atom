const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import zoomHealthHandler from "@/pages/api/integrations/zoom/health";
import nextjsHealthHandler from "@/pages/api/nextjs/health";
import googleWorkspaceHealthHandler from "@/pages/api/integrations/google-workspace/health";
import microsoft365HealthHandler from "@/pages/api/integrations/microsoft365/health";
import tableauHealthHandler from "@/pages/api/integrations/tableau/health";
import teamsHealthHandler from "@/pages/api/integrations/teams/health";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

const resetEnv = () => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
};

describe("pages/api/integrations/zoom/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (method = "GET") => {
    const { req, res } = createMocks({ method: method as RequestMethod }) as any;
    await zoomHealthHandler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns the backend health payload when healthy", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ status: "healthy", service: "zoom" }, true),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ status: "healthy", service: "zoom" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/zoom/v1/health",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("mirrors the backend status when unhealthy", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 503));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      ok: false,
      status: "unhealthy",
      error: "Backend Zoom service not responding",
    });
  });

  it("returns 503 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("zoom unreachable"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      ok: false,
      status: "unhealthy",
      error: "Zoom service unavailable",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/nextjs/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (method = "GET") => {
    const { req, res } = createMocks({ method: method as RequestMethod }) as any;
    await nextjsHealthHandler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("DELETE");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns the backend payload when healthy", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:5059";
    mockFetch.mockResolvedValue(
      jsonResponse({ status: "healthy", checks: {} }, true),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ status: "healthy", checks: {} });
    expect(mockFetch).toHaveBeenCalledWith("http://backend:5059/health", {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
  });

  it("reports the backend error message when the backend is unhealthy", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ error: "database offline" }, false, 503),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      services: {
        nextjs: { status: "unhealthy", error: "database offline" },
      },
    });
  });

  it("falls back to a generic error message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 500));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      services: {
        nextjs: { status: "unhealthy", error: "Service unavailable" },
      },
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("connection reset"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      services: {
        nextjs: { status: "unhealthy", error: "Internal server error" },
      },
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/google-workspace/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await googleWorkspaceHealthHandler(req, res);
    return res;
  };

  it("reports every service healthy when all backend probes succeed", async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.backend).toBe("connected");
    expect(body.connected_count).toBe(4);
    expect(body.total_services).toBe(4);
    expect(body.services).toEqual({
      drive: { status: "healthy", connected: true },
      gmail: { status: "healthy", connected: true },
      calendar: { status: "healthy", connected: true },
      workspace: { status: "healthy", connected: true },
    });
    const requestedUrls = mockFetch.mock.calls.map((c: any[]) => c[0]);
    expect(requestedUrls).toEqual([
      "http://127.0.0.1:8000/api/google-drive/health",
      "http://127.0.0.1:8000/api/gmail/health",
      "http://127.0.0.1:8000/api/calendar/health",
      "http://127.0.0.1:8000/api/google-workspace/health",
    ]);
  });

  it("reports healthy overall when at least one probe succeeds", async () => {
    mockFetch.mockImplementation((url: string) =>
      jsonResponse({}, url.includes("/api/gmail/health")),
    );
    const res = await invoke();
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.connected_count).toBe(1);
    expect(body.services.gmail).toEqual({ status: "healthy", connected: true });
    expect(body.services.drive).toEqual({
      status: "unhealthy",
      connected: false,
    });
  });

  it("reports disconnected when every probe fails", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    const res = await invoke();
    const body = res._getJSONData();
    expect(body.status).toBe("disconnected");
    expect(body.connected_count).toBe(0);
  });

  it("returns 503 when a backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("workspace down"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      status: "unhealthy",
      error: "Google Workspace services unavailable",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/microsoft365/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await microsoft365HealthHandler(req, res);
    return res;
  };

  it("marks outlook, teams and onedrive healthy when the backend responds ok", async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 200 });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.connected_count).toBe(3);
    expect(body.total_services).toBe(3);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/microsoft365/health",
      expect.anything(),
      );
  });

  it("marks every service disconnected when the backend responds not-ok", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 503 });
    const res = await invoke();
    const body = res._getJSONData();
    expect(body.status).toBe("disconnected");
    expect(body.connected_count).toBe(0);
    expect(body.services.outlook.connected).toBe(false);
  });

  it("returns 503 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("m365 unavailable"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      status: "unhealthy",
      error: "Microsoft 365 services unavailable",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/tableau/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await tableauHealthHandler(req, res);
    return res;
  };

  it("reports both services healthy when both probes succeed", async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const res = await invoke();
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.connected_count).toBe(2);
    expect(body.services).toEqual({
      auth: { status: "healthy", connected: true },
      api: { status: "healthy", connected: true },
    });
    expect(mockFetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/tableau/health", {
      method: "HEAD",
    });
  });

  it("marks only the api healthy when the HEAD probe fails", async () => {
    // The HEAD probe and the GET probe hit the same URL; tell them apart by method.
    mockFetch.mockImplementation((url: string, opts?: any) => ({
      ok: opts?.method !== "HEAD",
    }));
    const res = await invoke();
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.connected_count).toBe(1);
    expect(body.services.auth).toEqual({ status: "unhealthy", connected: false });
    expect(body.services.api).toEqual({ status: "healthy", connected: true });
  });

  it("reports disconnected when both probes fail", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    const res = await invoke();
    const body = res._getJSONData();
    expect(body.status).toBe("disconnected");
    expect(body.connected_count).toBe(0);
  });

  it("returns 503 when a backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("tableau down"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      status: "unhealthy",
      error: "Tableau services unavailable",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/teams/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await teamsHealthHandler(req, res);
    return res;
  };

  it("reports connected when the backend reports a connected status", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ status: "connected" }, true, 200),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      status: "healthy",
      connected: true,
      service: "Microsoft Teams",
      backend_response: { status: "connected" },
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/teams/status",
      expect.anything(),
      );
  });

  it("reports disconnected when the backend reports another status", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ status: "disconnected" }, true, 200),
    );
    const res = await invoke();
    expect(res._getJSONData().connected).toBe(false);
    expect(res._getJSONData().backend_response).toEqual({
      status: "disconnected",
    });
  });

  it("falls back to a mocked healthy response on backend failure", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 500));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.connected).toBe(true);
    expect(body.note).toBe("Mocked successful response due to backend failure");
  });

  it("falls back to a mocked healthy response on network failure", async () => {
    mockFetch.mockRejectedValue(new Error("teams unreachable"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.connected).toBe(true);
    expect(body.note).toBe("Mocked successful response due to network failure");
    expect(console.error).toHaveBeenCalled();
  });
});
