import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/accounting/scenario";

const mockFetch = jest.fn();

function jsonFetch(ok: boolean, status: number, body: any) {
  return {
    ok,
    status,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
    json: async () => body,
  } as any;
}

describe("pages/api/accounting/scenario", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (method: RequestMethod = "POST", query: any = {}, headers: any = {}) => {
    const { req, res } = createMocks({ method, query, headers }) as any;
    await handler(req, res);
    return res;
  };

  it("analyzes a scenario with defaults and forwards auth", async () => {
    mockFetch.mockResolvedValue(
      jsonFetch(true, 200, { data: { impact: -5000, confidence: 0.8 } }),
    );
    const res = await invoke("POST", {}, { authorization: "Bearer tok" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ impact: -5000, confidence: 0.8 });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain(
      "/api/ai-accounting/scenario?workspace_id=default&scenario_description=",
    );
    expect(options.method).toBe("POST");
    expect(options.headers).toEqual({ Authorization: "Bearer tok" });
  });

  it("encodes the workspace id and scenario description", async () => {
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { data: {} }));
    const res = await invoke("POST", {
      workspace_id: "acme corp",
      scenario_description: "What if revenue drops 20%?",
    });
    expect(res._getStatusCode()).toBe(200);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("workspace_id=acme corp");
    expect(url).toContain(
      `scenario_description=${encodeURIComponent("What if revenue drops 20%?")}`,
    );
    // No authorization header on the request -> none forwarded.
    expect(mockFetch.mock.calls[0][1].headers).toEqual({});
  });

  it("passes through the backend status (e.g. 401) with a generic error", async () => {
    mockFetch.mockResolvedValue(jsonFetch(false, 401, "invalid token"));
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      error: "Failed to analyze scenario from backend",
    });
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining("Backend returned 401"),
    );
  });

  it("returns 500 when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal server error while analyzing scenario",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 405 for non-POST methods", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
