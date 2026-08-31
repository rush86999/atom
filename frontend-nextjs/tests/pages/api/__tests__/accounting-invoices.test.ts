import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/accounting/invoices";

const mockFetch = jest.fn();

function jsonFetch(ok: boolean, status: number, body: any) {
  return {
    ok,
    status,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
    json: async () => body,
  } as any;
}

describe("pages/api/accounting/invoices", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
  });

  const invoke = async (method = "GET", query: any = {}, body: any = {}, headers: any = {}) => {
    const { req, res } = createMocks({ method: method as RequestMethod, query, body, headers }) as any;
    await handler(req, res);
    return res;
  };

  it("proxies GET download and streams a PDF buffer", async () => {
    const blob = new Blob(["%PDF-1.4 fake pdf"]);
    mockFetch.mockResolvedValue({
      ok: true,
      blob: async () => blob,
    });
    const res = await invoke("GET", { action: "download", type: "ar", invoice_id: "inv-1" }, {}, { authorization: "Bearer tok" });
    expect(res._getStatusCode()).toBe(200);
    expect(res.getHeader("Content-Type")).toBe("application/pdf");
    expect(res.getHeader("Content-Disposition")).toContain(
      "invoice_inv-1.pdf",
    );
    const data = res._getData();
    expect(Buffer.isBuffer(data)).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/apar/ar/inv-1/download"),
      expect.objectContaining({ headers: { Authorization: "Bearer tok" } }),
    );
  });

  it("passes through the backend status on failed download", async () => {
    mockFetch.mockResolvedValue(jsonFetch(false, 404, "Invoice not found"));
    const res = await invoke("GET", { action: "download", type: "ap", invoice_id: "x" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData().error).toContain("Invoice not found");
  });

  it("fetches all invoices by default", async () => {
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { invoices: [{ id: 1 }] }));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ invoices: [{ id: 1 }] });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/apar/all"),
      expect.anything(),
    );
  });

  it("passes through the backend status when fetching invoices fails", async () => {
    mockFetch.mockResolvedValue(jsonFetch(false, 500, "backend exploded"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().error).toContain("backend exploded");
  });

  it("proxies POST generate with the request body", async () => {
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { invoice: "gen-1" }));
    const body = { customer_id: 7, lines: [] };
    const res = await invoke("POST", { action: "generate" }, body);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ invoice: "gen-1" });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/apar/ar/generate"),
      expect.objectContaining({ method: "POST", body: JSON.stringify(body) }),
    );
  });

  it("proxies POST send for a specific invoice", async () => {
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { sent: true }));
    const res = await invoke("POST", { action: "send", invoice_id: "inv-9" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ sent: true });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/apar/ar/inv-9/send"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("passes through backend errors on POST actions", async () => {
    mockFetch.mockResolvedValue(jsonFetch(false, 422, "invalid payload"));
    const res = await invoke("POST", { action: "generate" }, {});
    expect(res._getStatusCode()).toBe(422);
    expect(res._getJSONData().error).toContain("invalid payload");
  });

  it("returns 400 for an unknown POST action", async () => {
    const res = await invoke("POST", { action: "explode" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe(
      "Invalid action provided for POST method",
    );
  });

  it("returns 405 for unsupported methods", async () => {
    const res = await invoke("PUT");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData().error).toBe("Method not allowed");
  });

  it("returns 500 when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().error).toBe("Failed to process invoice request");
  });
});
