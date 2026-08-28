const mockExistsSync = jest.fn();
const mockReadFileSync = jest.fn();
jest.mock("fs", () => ({
  existsSync: mockExistsSync,
  readFileSync: mockReadFileSync,
}));

const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/dev/bootstrap-session";

const PASSWORD_FILE_SUFFIX = "bootstrap_admin_password.txt";

function backendJson(body: any, ok = true, status = 200): any {
  return { ok, status, json: async () => body };
}

describe("pages/api/dev/bootstrap-session", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    (process.env as any).NODE_ENV = "test";
    // Both candidate password files exist and contain a secret by default.
    mockExistsSync.mockImplementation(
      (p: any) => typeof p === "string" && p.includes(PASSWORD_FILE_SUFFIX),
    );
    mockReadFileSync.mockReturnValue("  bootstrap-secret \n");
  });

  afterEach(() => {
    (process.env as any).NODE_ENV = "test";
  });

  const invoke = async (method: any = "GET") => {
    const { req, res } = createMocks({ method }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 404 in production", async () => {
    (process.env as any).NODE_ENV = "production";
    const res = await invoke();
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "not_found" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "method_not_allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 404 when no bootstrap password file exists", async () => {
    mockExistsSync.mockReturnValue(false);
    const res = await invoke();
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "bootstrap_password_not_found" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("skips candidate files whose password is blank", async () => {
    mockReadFileSync.mockReturnValue("   ");
    const res = await invoke();
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "bootstrap_password_not_found" });
    // Both candidates were tried before giving up.
    expect(mockReadFileSync).toHaveBeenCalledTimes(2);
  });

  it("skips candidate files that cannot be read", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("EACCES");
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "bootstrap_password_not_found" });
  });

  it("logs in with the trimmed password and returns the token", async () => {
    mockFetch.mockResolvedValue(backendJson({ access_token: "tok-1" }));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      access_token: "tok-1",
      email: "admin@example.com",
    });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/auth/login");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      username: "admin@example.com",
      password: "bootstrap-secret",
    });
  });

  it("returns 401 when the login response is not ok", async () => {
    mockFetch.mockResolvedValue(backendJson({ detail: "bad credentials" }, false, 401));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      error: "bootstrap_login_failed",
      detail: "bad credentials",
    });
  });

  it("returns 401 with the default detail when the response has no token", async () => {
    mockFetch.mockResolvedValue(backendJson({ user: "admin" }));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      error: "bootstrap_login_failed",
      detail: "Could not authenticate the bootstrap user",
    });
  });

  it("returns 401 with the default detail when the response body is not JSON", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error("invalid json");
      },
    });
    const res = await invoke();
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      error: "bootstrap_login_failed",
      detail: "Could not authenticate the bootstrap user",
    });
  });

  it("returns 500 when the login request throws", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "bootstrap_login_error",
      detail: "ECONNREFUSED",
    });
  });
});
