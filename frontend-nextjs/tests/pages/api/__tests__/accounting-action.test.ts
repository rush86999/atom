import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/accounting/action";

const mockFetch = jest.fn();

function jsonFetch(ok: boolean, status: number, body: any) {
  return {
    ok,
    status,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
    json: async () => body,
  } as any;
}

describe("pages/api/accounting/action", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (
    method: RequestMethod = "POST",
    query: any = {},
    body: any = undefined,
    headers: any = {},
  ) => {
    const { req, res } = createMocks({ method, query, body, headers }) as any;
    await handler(req, res);
    return res;
  };

  it("proxies POST for the post action with the transaction id", async () => {
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { posted: true }));
    const body = { memo: "approved" };
    const res = await invoke(
      "POST",
      { action: "post", id: "tx-9" },
      body,
      { authorization: "Bearer tok" },
    );
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ posted: true });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/ai-accounting/post/tx-9");
    expect(options.method).toBe("POST");
    expect(options.headers).toEqual({
      Authorization: "Bearer tok",
      "Content-Type": "application/json",
    });
    expect(options.body).toBe(JSON.stringify(body));
  });

  it("proxies POST for the categorize action without a body", async () => {
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { categorized: 3 }));
    // node-mocks-http defaults req.body to {} (truthy); use _setBody to
    // exercise the falsy-body branch in the handler.
    const { req, res } = createMocks({ method: "POST", query: { action: "categorize" } }) as any;
    req._setBody("");
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ categorized: 3 });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/ai-accounting/categorize");
    expect(options.headers).toEqual({ "Content-Type": "application/json" });
    expect(options.body).toBeUndefined();
  });

  it("returns 400 when the action is unknown", async () => {
    const res = await invoke("POST", { action: "delete" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      error: "Invalid action or missing ID",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the post action has no id", async () => {
    const res = await invoke("POST", { action: "post" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Invalid action or missing ID");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("passes through the backend status (e.g. 401) and error body", async () => {
    mockFetch.mockResolvedValue(jsonFetch(false, 401, "unauthorized"));
    const res = await invoke("POST", { action: "categorize" });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ error: "unauthorized" });
  });

  it("returns 500 with the action name when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("POST", { action: "post", id: "tx-1" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ error: "Failed to perform post" });
    expect(console.error).toHaveBeenCalled();
  });

  it("returns 405 for non-POST methods", async () => {
    const res = await invoke("GET", { action: "categorize" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
