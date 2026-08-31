const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import analyticsHandler from "@/pages/api/hubspot/analytics";
import ticketsHandler from "@/pages/api/integrations/hubspot/tickets";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/hubspot/analytics", () => {
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
    await analyticsHandler(req, res);
    return res;
  };

  it("forwards GET requests without a body", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ visits: 42, contacts: 7 }, true, 200),
    );
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ visits: 42, contacts: 7 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/analytics",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        body: undefined,
      },
    );
  });

  it("forwards POST requests with the JSON body", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ report: "funnel", rows: [] }, true, 200),
    );
    const res = await invoke("POST", { report_type: "funnel", date_range: "30d" });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch.mock.calls[0][1]).toEqual({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_type: "funnel", date_range: "30d" }),
    });
  });

  it("honours PYTHON_API_SERVICE_BASE_URL and mirrors backend errors", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
    mockFetch.mockResolvedValue(
      jsonResponse({ error: "hubspot unauthorized" }, false, 401),
    );
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "hubspot unauthorized" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5058/api/hubspot/analytics",
    );
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("hubspot offline"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch HubSpot analytics",
      message: "hubspot offline",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/hubspot/tickets", () => {
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
    await ticketsHandler(req, res);
    return res;
  };

  it("proxies the body with the current user id and returns the payload", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ results: [{ id: "t1" }], total: 1 }, true, 200),
    );
    const res = await invoke({ limit: 10, user_id: "ignored" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ results: [{ id: "t1" }], total: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/tickets",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
        body: JSON.stringify({ limit: 10, user_id: "current" }),
      },
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL and mirrors backend errors", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:5058";
    mockFetch.mockResolvedValue(
      jsonResponse({ error: "expired portal token" }, false, 403),
    );
    const res = await invoke({ limit: 5 });
    expect(res._getStatusCode()).toBe(403);
    expect(res._getJSONData()).toEqual({ error: "expired portal token" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:5058/api/hubspot/tickets",
    );
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("tickets boom"));
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch HubSpot tickets",
      message: "tickets boom",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
