const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import projectsHandler from "@/pages/api/integrations/figma/projects";
import searchHandler from "@/pages/api/integrations/figma/search";
import healthHandler from "@/pages/api/integrations/figma/health";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

describe("pages/api/integrations/figma/projects", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (body?: any, method = "POST") => {
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await projectsHandler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(undefined, "GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getData()).toBe("Method GET Not Allowed");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("forwards the body to the backend and returns 200 on success", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ success: true, projects: [{ id: "f1" }] }, true),
    );
    const res = await invoke({ user_id: "u1", limit: 5 });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      projects: [{ id: "f1" }],
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/figma/projects",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "u1", limit: 5 }),
      },
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL and mirrors backend failures with 400", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:6000";
    mockFetch.mockResolvedValue(
      jsonResponse({ success: false, error: "bad figma token" }, false, 401),
    );
    const res = await invoke({ user_id: "u1" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "bad figma token",
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:6000/api/figma/projects",
    );
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("backend down"));
    const res = await invoke({ user_id: "u1" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Endpoint failed",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/figma/search", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (body?: any, method = "POST") => {
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await searchHandler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke(undefined, "PUT");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getData()).toBe("Method PUT Not Allowed");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("forwards the search body and returns 200 on success", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ success: true, files: [{ id: "file-1" }] }, true),
    );
    const res = await invoke({ query: "onboarding", max_results: 10 });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      files: [{ id: "file-1" }],
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/figma/search",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: "onboarding", max_results: 10 }),
      },
    );
  });

  it("mirrors backend error payloads with 400", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ success: false, error: "invalid query" }, false, 422),
    );
    const res = await invoke({ query: "" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "invalid query",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("network gone"));
    const res = await invoke({ query: "x" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Endpoint failed",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/figma/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (method = "GET") => {
    const { req, res } = createMocks({ method: method as RequestMethod }) as any;
    await healthHandler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getData()).toBe("Method POST Not Allowed");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns the backend health payload", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ status: "healthy", service: "figma" }, true),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      status: "healthy",
      service: "figma",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/integrations/figma/health",
      { headers: {} },
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://backend:7000";
    mockFetch.mockResolvedValue(jsonResponse({ status: "unhealthy" }, false, 503));
    const res = await invoke();
    // The handler passes the payload through with 200 regardless of backend status.
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ status: "unhealthy" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend:7000/api/integrations/figma/health",
    );
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Health check failed",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
