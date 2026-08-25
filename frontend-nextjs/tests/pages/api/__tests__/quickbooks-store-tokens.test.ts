const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/quickbooks/auth/store-tokens";

function backendResponse(ok: boolean, data: any, status = ok ? 200 : 400): any {
  return { ok, status, json: async () => data };
}

const validBody = {
  user_id: "user-1",
  access_token: "at-quickbooks",
  refresh_token: "rt-quickbooks",
  expires_at: "2026-12-31T00:00:00Z",
  realm_id: "realm-1",
};

describe("pages/api/quickbooks/auth/store-tokens", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
    delete process.env.PYTHON_API_SERVICE_BASE_URL;
  });

  const invoke = async (method: any = "POST", body: any = validBody) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 for non-POST methods", async () => {
    const res = await invoke("PUT");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({
      error: "Method not allowed",
      message: "Only POST method is allowed for storing tokens",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when user_id is missing", async () => {
    const res = await invoke("POST", { ...validBody, user_id: undefined });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Missing required fields",
      message: "user_id, access_token, and realm_id are required",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when access_token is missing", async () => {
    const res = await invoke("POST", { ...validBody, access_token: undefined });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Missing required fields");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when realm_id is missing", async () => {
    const res = await invoke("POST", { ...validBody, realm_id: undefined });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Missing required fields");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("forwards the tokens to the backend and returns success", async () => {
    mockFetch.mockResolvedValue(backendResponse(true, { stored: true }));
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      message: "QuickBooks tokens stored successfully",
    });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/quickbooks/auth/store-tokens");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual(validBody);
  });

  it("passes through the backend failure with its message", async () => {
    mockFetch.mockResolvedValue(
      backendResponse(false, { message: "invalid realm" }, 422),
    );
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(422);
    expect(res._getJSONData()).toEqual({
      error: "Failed to store tokens in backend",
      message: "invalid realm",
    });
  });

  it("uses a generic message when the backend error has none", async () => {
    mockFetch.mockResolvedValue(backendResponse(false, {}, 500));
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to store tokens in backend",
      message: "Unknown backend error",
    });
  });

  it("returns 500 with the error message when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to store QuickBooks tokens",
      message: "ECONNREFUSED",
    });
    expect(console.error).toHaveBeenCalledWith(
      "QuickBooks token storage error:",
      expect.any(Error),
    );
  });

  it("returns 500 with a generic message when a non-Error is thrown", async () => {
    mockFetch.mockRejectedValue("boom");
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to store QuickBooks tokens",
      message: "Unknown error",
    });
  });
});
