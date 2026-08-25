const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

jest.mock("@/pages/api/auth/[...nextauth]", () => ({
  authOptions: { providers: [] },
}));

const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import docsHandler from "@/pages/api/integrations/google-workspace/docs";
import authStartHandler from "@/pages/api/integrations/google-workspace/auth/start";

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
});

describe("pages/api/integrations/google-workspace/docs", () => {
  const invoke = async (method = "GET", query: any = {}, body?: any) => {
    const { req, res } = createMocks({ method, query, body }) as any;
    await docsHandler(req, res);
    return res;
  };

  it("proxies a plain GET list request to the backend", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(true, 200, { docs: [{ id: "d1" }] }),
    );
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ docs: [{ id: "d1" }] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/google-workspace/docs",
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "x-user-id": "current",
        },
        body: undefined,
      },
    );
  });

  it("appends the id path segment for a single id", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, { id: "d1" }));
    await invoke("GET", { id: "d1" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/google-workspace/docs/d1",
    );
  });

  it("ignores array ids and forwards remaining query params", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET", { id: ["1", "2"], pageSize: "10" });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/google-workspace/docs?pageSize=10");
  });

  it("sends the request body for non-GET methods", async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, 201, { id: "new" }));
    const res = await invoke("POST", {}, { title: "New doc" });
    expect(res._getStatusCode()).toBe(201);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/google-workspace/docs",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-user-id": "current",
        },
        body: JSON.stringify({ title: "New doc" }),
      },
    );
  });

  it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
    process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5058";
    mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
    await invoke("GET");
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://python:5058/api/google-workspace/docs",
    );
  });

  it("mirrors the backend error status and payload", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(false, 404, { error: "Doc not found" }),
    );
    const res = await invoke("GET", { id: "missing" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "Doc not found" });
  });

  it("returns 500 with a friendly message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("backend exploded"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Google Docs",
      message: "backend exploded",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("reports Unknown error for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke("GET");
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch Google Docs",
      message: "Unknown error",
    });
  });
});

describe("pages/api/integrations/google-workspace/auth/start", () => {
  const mockSession = { user: { id: "user-1", email: "u@example.com" } };

  const invoke = async (session: any = mockSession, method = "GET") => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({
      method,
      url: "/api/integrations/google-workspace/auth/start",
    }) as any;
    await authStartHandler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke(mockSession, "POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockGetServerSession).not.toHaveBeenCalled();
  });

  it("redirects to signin when there is no session", async () => {
    const res = await invoke(null);
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain(
      "/auth/signin?callbackUrl=" +
        encodeURIComponent("/api/integrations/google-workspace/auth/start"),
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects to signin when the session has no user", async () => {
    const res = await invoke({ expires: "soon" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toContain("/auth/signin");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("redirects authenticated users to the backend OAuth initiate URL", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "http://127.0.0.1:8000/api/v1/auth/oauth/google/initiate",
    );
    expect(mockGetServerSession).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      { providers: [] },
    );
  });

  it("returns 500 when the redirect itself throws", async () => {
    mockGetServerSession.mockResolvedValue(mockSession);
    const { req, res } = createMocks({ method: "GET" }) as any;
    res.redirect = () => {
      throw new Error("headers already sent");
    };
    await authStartHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to initiate Google OAuth flow",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
