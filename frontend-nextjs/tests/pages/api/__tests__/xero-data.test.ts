const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import bankAccountsHandler from "@/pages/api/integrations/xero/bank_accounts";
import contactsHandler from "@/pages/api/integrations/xero/contacts";
import invoicesHandler from "@/pages/api/integrations/xero/invoices";

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
});

// All handlers in this family share the same unauthenticated proxy shape:
// `${backendUrl}${backendPath}[/${id}][?query]` with the request method and a
// JSON body for non-GET requests.
const runProxySuite = (
  describeName: string,
  handler: any,
  backendPath: string,
  failureMessage: string,
) => {
  describe(describeName, () => {
    const invoke = async (method = "GET", query: any = {}, body?: any) => {
      const { req, res } = createMocks({ method, query, body }) as any;
      await handler(req, res);
      return res;
    };

    it("proxies a plain GET list request to the backend", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse(true, 200, { items: [{ id: "x-1" }] }),
      );
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ items: [{ id: "x-1" }] });
      expect(mockFetch).toHaveBeenCalledWith(`http://127.0.0.1:8000${backendPath}`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        body: undefined,
      });
    });

    it("appends the id path segment for a single id", async () => {
      mockFetch.mockResolvedValue(jsonResponse(true, 200, { id: "x-1" }));
      await invoke("GET", { id: "x-1" });
      expect(mockFetch.mock.calls[0][0]).toBe(
        `http://127.0.0.1:8000${backendPath}/x-1`,
      );
    });

    it("ignores array ids and forwards remaining query params", async () => {
      mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
      await invoke("GET", { id: ["1", "2"], page: "2" });
      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe(`http://127.0.0.1:8000${backendPath}?page=2`);
    });

    it("sends the request body for non-GET methods", async () => {
      mockFetch.mockResolvedValue(jsonResponse(true, 201, { id: "new" }));
      const res = await invoke("POST", {}, { Name: "created" });
      expect(res._getStatusCode()).toBe(201);
      expect(mockFetch).toHaveBeenCalledWith(
        `http://127.0.0.1:8000${backendPath}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ Name: "created" }),
        },
      );
    });

    it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
      process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5058";
      mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
      await invoke("GET");
      expect(mockFetch.mock.calls[0][0]).toBe(`http://python:5058${backendPath}`);
    });

    it("mirrors the backend error status and payload", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse(false, 404, { error: "Not found" }),
      );
      const res = await invoke("GET", { id: "missing" });
      expect(res._getStatusCode()).toBe(404);
      expect(res._getJSONData()).toEqual({ error: "Not found" });
    });

    it("returns 500 with a friendly message when fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("backend exploded"));
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        error: failureMessage,
        message: "backend exploded",
      });
      expect(console.error).toHaveBeenCalled();
    });

    it("reports Unknown error for non-Error rejections", async () => {
      mockFetch.mockRejectedValue("boom");
      const res = await invoke("GET");
      expect(res._getJSONData()).toEqual({
        error: failureMessage,
        message: "Unknown error",
      });
    });
  });
};

runProxySuite(
  "pages/api/integrations/xero/bank_accounts",
  bankAccountsHandler,
  "/api/xero/bank_accounts",
  "Failed to fetch Xero bank accounts",
);

runProxySuite(
  "pages/api/integrations/xero/contacts",
  contactsHandler,
  "/api/xero/contacts",
  "Failed to fetch Xero contacts",
);

runProxySuite(
  "pages/api/integrations/xero/invoices",
  invoicesHandler,
  "/api/xero/invoices",
  "Failed to fetch Xero invoices",
);
