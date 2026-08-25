const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import hubspotStartHandler from "@/pages/api/hubspot/oauth/start";
import zendeskStartHandler from "@/pages/api/zendesk/oauth/start";
import msteamsStartHandler from "@/pages/api/msteams/oauth/start";
import zoomStartHandler from "@/pages/api/zoom/oauth/start";
import azureStartHandler from "@/pages/api/integrations/azure/auth/start";
import azureCallbackHandler from "@/pages/api/integrations/azure/auth/callback";
import linearStartHandler from "@/pages/api/integrations/linear/auth/start";

const jsonResponse = (data: any, ok: boolean, status = 200): any => ({
  ok,
  status,
  json: async () => data,
});

const resetEnv = () => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  delete process.env.MSTEAMS_CLIENT_ID;
  delete process.env.MSTEAMS_REDIRECT_URI;
  delete process.env.ZOOM_CLIENT_ID;
  delete process.env.ZOOM_REDIRECT_URI;
};

// Shared behaviour for the four backend-driven OAuth start routes
// (HubSpot, Zendesk, Linear) that follow the identical contract:
// GET <backend>/api/<provider>/auth/start -> { auth_url } -> redirect.
type BackendStartHandler = (req: any, res: any) => Promise<void>;

const backendStartCases: Array<[string, BackendStartHandler, string]> = [
  ["pages/api/hubspot/oauth/start", hubspotStartHandler, "http://127.0.0.1:8000/api/hubspot/auth/start"],
  ["pages/api/zendesk/oauth/start", zendeskStartHandler, "http://127.0.0.1:8000/api/zendesk/auth/start"],
  ["pages/api/integrations/linear/auth/start", linearStartHandler, "http://127.0.0.1:8000/api/integrations/linear/auth/start"],
];

backendStartCases.forEach(([label, handler, backendPath]) => {
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

    it("redirects to the authorization URL returned by the backend", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ auth_url: "https://provider.example/oauth/authorize" }, true),
      );
      const res = await invoke();
      expect(res._getStatusCode()).toBe(302);
      expect(res._getRedirectUrl()).toBe(
        "https://provider.example/oauth/authorize",
      );
      expect(mockFetch).toHaveBeenCalledWith(backendPath, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
    });

    it("returns 500 when the backend responds without an auth_url", async () => {
      mockFetch.mockResolvedValue(jsonResponse({}, true));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData().message).toBe(
        "No authorization URL returned from backend",
      );
    });

    it("returns 500 when the backend responds with an error status", async () => {
      mockFetch.mockResolvedValue(jsonResponse({}, false, 503));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData().message).toContain(
        "Failed to contact",
      );
    });

    it("returns 500 when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("backend unreachable"));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData().message).toBe("backend unreachable");
      expect(console.error).toHaveBeenCalled();
    });
  });
});

describe("pages/api/msteams/oauth/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    msteamsStartHandler(req, res);
    return res;
  };

  it("returns 500 when Microsoft Teams environment variables are missing", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Microsoft Teams environment variables not configured.",
    });
  });

  it("redirects to the Microsoft authorize endpoint when configured", async () => {
    process.env.MSTEAMS_CLIENT_ID = "ms-client";
    process.env.MSTEAMS_REDIRECT_URI = "http://localhost:3000/api/msteams/callback";
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=ms-client&response_type=code&redirect_uri=http://localhost:3000/api/msteams/callback&response_mode=query&scope=offline_access User.Read Mail.ReadWrite Calendars.ReadWrite&state=some-random-state",
    );
  });
});

describe("pages/api/zoom/oauth/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    zoomStartHandler(req, res);
    return res;
  };

  it("returns 500 when Zoom environment variables are missing", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Zoom environment variables not configured.",
    });
  });

  it("redirects to the Zoom authorize endpoint when configured", async () => {
    process.env.ZOOM_CLIENT_ID = "zoom-client";
    process.env.ZOOM_REDIRECT_URI = "http://localhost:3000/api/zoom/callback";
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://zoom.us/oauth/authorize?response_type=code&client_id=zoom-client&redirect_uri=http://localhost:3000/api/zoom/callback&state=some-random-state",
    );
  });
});

describe("pages/api/integrations/azure/auth/start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await azureStartHandler(req, res);
    return res;
  };

  it("posts to the backend and redirects to the authorization URL", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(
        { authorization_url: "https://login.microsoftonline.com/oauth" },
        true,
      ),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe(
      "https://login.microsoftonline.com/oauth",
    );
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/azure/start",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          redirect_uri:
            "undefined/api/integrations/azure/auth/callback",
        }),
      },
    );
  });

  it("builds the redirect_uri from NEXT_PUBLIC_API_BASE_URL when set", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://frontend:3000";
    mockFetch.mockResolvedValue(
      jsonResponse({ authorization_url: "https://azure.example" }, true),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(JSON.parse(mockFetch.mock.calls[0][1].body).redirect_uri).toBe(
      "http://frontend:3000/api/integrations/azure/auth/callback",
    );
  });

  it("returns 500 when the backend responds without an authorization_url", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, true));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to get Azure authorization URL",
      message: "No authorization URL returned from backend",
    });
  });

  it("returns 500 when the backend responds with an error status", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 500));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Backend Azure service error",
      message: "Failed to contact Azure authentication service",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("azure down"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to start Azure OAuth flow",
      message: "azure down",
    });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("pages/api/integrations/azure/auth/callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetEnv();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(resetEnv);

  const invoke = async (query: any = { code: "az-code", state: "az-state" }) => {
    const { req, res } = createMocks({ method: "GET", query }) as any;
    await azureCallbackHandler(req, res);
    return res;
  };

  it("exchanges the code and redirects to the success page", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ ok: true, access_token: "at" }, true),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(302);
    expect(res._getRedirectUrl()).toBe("/integrations/azure?success=true");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/auth/azure/callback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: "az-code",
          state: "az-state",
          user_id: "current",
        }),
      },
    );
  });

  it("returns 400 with the backend message on failure", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ message: "code expired" }, false, 400),
    );
    const res = await invoke();
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Azure OAuth",
      message: "code expired",
    });
  });

  it("falls back to a generic message when the backend omits one", async () => {
    mockFetch.mockResolvedValue(jsonResponse({}, false, 500));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Azure OAuth",
      message: "Unknown OAuth error",
    });
  });

  it("returns 500 when the backend fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("callback boom"));
    const res = await invoke();
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to complete Azure OAuth flow",
      message: "callback boom",
    });
    expect(console.error).toHaveBeenCalled();
  });
});
