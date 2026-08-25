import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/google-workspace/auth/callback";

const expectedBase =
  process.env.PYTHON_API_SERVICE_BASE_URL || "http://127.0.0.1:8000";

describe("pages/api/integrations/google-workspace/auth/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method: any = "GET", query: any = {}) => {
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return { req, res };
  };

  it("rejects non-GET methods with 405", async () => {
    const { res } = await invoke("POST", { code: "c" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("redirects with the encoded provider error when Google reports one", async () => {
    const { res } = await invoke("GET", { error: "access denied" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      `/integrations?error=${encodeURIComponent("access denied")}`,
    );
    expect(console.error).toHaveBeenCalledWith(
      "Google OAuth error from provider:",
      "access denied",
    );
  });

  it("returns 400 when the authorization code is missing", async () => {
    const { res } = await invoke("GET", { state: "s" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Missing authorization code" });
  });

  it("redirects to the backend callback with code and state", async () => {
    const { res } = await invoke("GET", { code: "c-1", state: "st-1" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      `${expectedBase}/api/v1/auth/oauth/google/callback?code=c-1&state=st-1`,
    );
  });

  it("omits the state query param when no state is provided", async () => {
    const { res } = await invoke("GET", { code: "c-2" });
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      `${expectedBase}/api/v1/auth/oauth/google/callback?code=c-2`,
    );
  });

  it("returns 500 when building or issuing the redirect fails", async () => {
    const { req, res } = createMocks({
      method: "GET",
      query: { code: "c-3", state: "s" },
    }) as any;
    res.redirect = jest.fn(() => {
      throw new Error("redirect failed");
    });
    await handler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to process Google OAuth callback",
    });
    expect(console.error).toHaveBeenCalledWith(
      "Failed to process Google OAuth callback:",
      expect.any(Error),
    );
  });
});
