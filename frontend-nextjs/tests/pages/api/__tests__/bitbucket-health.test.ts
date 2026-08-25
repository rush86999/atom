const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/bitbucket/health";

const okResponse = (data: any): any => ({
  ok: true,
  status: 200,
  json: async () => data,
});

const failingResponse = (status: number, data: any): any => ({
  ok: false,
  status,
  json: async () => data,
});

describe("pages/api/integrations/bitbucket/health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (query: any = {}, method = "GET") => {
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke({ access_token: "tok" }, "POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when no access token is provided", async () => {
    const res = await invoke({});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Access token required",
      details: "Please provide Bitbucket access token",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("forwards the token to the backend and returns healthy data", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ status: "healthy", user: "u@example.com" }),
    );
    const res = await invoke({ access_token: "bb-token" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      status: "healthy",
      user: "u@example.com",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/bitbucket/health",
      {
        method: "GET",
        headers: {
          Authorization: "Bearer bb-token",
          "Content-Type": "application/json",
        },
      },
    );
  });

  it("mirrors the backend failure status and detail when unhealthy", async () => {
    mockFetch.mockResolvedValue(
      failingResponse(401, { detail: "Invalid access token" }),
    );
    const res = await invoke({ access_token: "bad" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      error: "Bitbucket health check failed",
      details: "Invalid access token",
    });
  });

  it("defaults the failure details when the backend omits detail", async () => {
    mockFetch.mockResolvedValue(failingResponse(503, {}));
    const res = await invoke({ access_token: "tok" });
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData()).toEqual({
      error: "Bitbucket health check failed",
      details: "Unknown error",
    });
  });

  it("returns 500 with a message when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const res = await invoke({ access_token: "tok" });
    expect(res._getStatusCode()).toBe(500);
    const body = res._getJSONData();
    expect(body.error).toBe("Bitbucket service unavailable");
    expect(body.details).toBe("connection refused");
    expect(typeof body.timestamp).toBe("string");
    expect(console.error).toHaveBeenCalled();
  });

  it("falls back to 'Unknown error' details for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("nope");
    const res = await invoke({ access_token: "tok" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().details).toBe("Unknown error");
  });
});
