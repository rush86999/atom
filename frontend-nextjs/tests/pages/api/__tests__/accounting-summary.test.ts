import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/accounting/summary";

const mockFetch = jest.fn();

function jsonFetch(ok: boolean, status: number, body: any) {
  return {
    ok,
    status,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
    json: async () => body,
  } as any;
}

describe("pages/api/accounting/summary", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (method = "GET", headers: any = {}) => {
    const { req, res } = createMocks({ method: method as RequestMethod, headers }) as any;
    await handler(req, res);
    return res;
  };

  it("proxies GET to the backend dashboard summary endpoint", async () => {
    mockFetch.mockResolvedValue(
      jsonFetch(true, 200, { summary: { revenue: 100, expenses: 40 } }),
    );
    const res = await invoke("GET", { authorization: "Bearer tok" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ summary: { revenue: 100, expenses: 40 } });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/ai-accounting/dashboard/summary");
    expect(options.headers).toEqual({
      Authorization: "Bearer tok",
      "Content-Type": "application/json",
    });
  });

  it("omits the Authorization header when the request has none", async () => {
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { summary: {} }));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch.mock.calls[0][1].headers).toEqual({
      "Content-Type": "application/json",
    });
  });

  it("passes through the backend status (e.g. 401) and error body", async () => {
    mockFetch.mockResolvedValue(jsonFetch(false, 401, "token expired"));
    const res = await invoke("GET", { authorization: "Bearer bad" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "token expired" });
  });

  it("returns 500 when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch accounting summary",
    });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 405 for non-GET methods", async () => {
    const res = await invoke("PUT");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
