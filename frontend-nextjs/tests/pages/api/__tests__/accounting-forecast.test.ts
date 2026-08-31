import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/accounting/forecast";

const mockFetch = jest.fn();

function jsonFetch(ok: boolean, status: number, body: any) {
  return {
    ok,
    status,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
    json: async () => body,
  } as any;
}

describe("pages/api/accounting/forecast", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (method = "GET", query: any = {}, headers: any = {}) => {
    const { req, res } = createMocks({ method: method as RequestMethod, query, headers }) as any;
    await handler(req, res);
    return res;
  };

  it("fetches the forecast with the default workspace and forwards auth", async () => {
    mockFetch.mockResolvedValue(
      jsonFetch(true, 200, { data: [{ month: "2026-09", cash: 1200 }] }),
    );
    const res = await invoke("GET", {}, { authorization: "Bearer tok" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual([{ month: "2026-09", cash: 1200 }]);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/ai-accounting/forecast?workspace_id=default");
    expect(options.method).toBe("GET");
    expect(options.headers).toEqual({ Authorization: "Bearer tok" });
  });

  it("uses the workspace_id query parameter when provided", async () => {
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { data: [] }));
    const res = await invoke("GET", { workspace_id: "acme" });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch.mock.calls[0][0]).toContain(
      "workspace_id=acme",
    );
    // No authorization header on the request -> none forwarded.
    expect(mockFetch.mock.calls[0][1].headers).toEqual({});
  });

  it("passes through the backend status (e.g. 401) with a generic error", async () => {
    mockFetch.mockResolvedValue(jsonFetch(false, 401, "invalid token"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch forecast from backend",
    });
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining("Backend returned 401"),
    );
  });

  it("returns 500 when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Internal server error while fetching forecast",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 405 for non-GET methods", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
