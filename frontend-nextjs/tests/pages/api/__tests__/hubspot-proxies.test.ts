import { createMocks } from "node-mocks-http";
import dealsHandler from "@/pages/api/integrations/hubspot/deals";
import companiesHandler from "@/pages/api/integrations/hubspot/companies";
import contactsHandler from "@/pages/api/integrations/hubspot/contacts";

const mockFetch = jest.fn();

const okJson = (data: any): any => ({ status: 200, json: async () => data });
const errJson = (status: number, data: any): any => ({ status, json: async () => data });

describe("pages/api/integrations/hubspot/deals", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("forwards the request body to the backend and returns its payload", async () => {
    mockFetch.mockResolvedValue(okJson({ results: [{ id: "d1" }] }));
    const { req, res } = createMocks({
      method: "POST",
      body: { dealName: "Big Deal" },
    }) as any;
    await dealsHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ results: [{ id: "d1" }] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/deals",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
        body: JSON.stringify({ dealName: "Big Deal", user_id: "current" }),
      },
    );
  });

  it("mirrors the backend status when it errors", async () => {
    mockFetch.mockResolvedValue(errJson(422, { detail: "bad" }));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await dealsHandler(req, res);
    expect(res._getStatusCode()).toBe(422);
    expect(res._getJSONData()).toEqual({ detail: "bad" });
  });

  it("returns 500 with a generic message when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await dealsHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch HubSpot deals",
      message: "connection refused",
    });
  });

  it("falls back to Unknown error for non-Error rejections", async () => {
    mockFetch.mockRejectedValue("boom");
    const { req, res } = createMocks({ method: "POST", body: {} }) as any;
    await dealsHandler(req, res);
    expect(res._getJSONData().message).toBe("Unknown error");
  });
});

describe("pages/api/integrations/hubspot/companies", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("defaults limit/offset/user_id and forwards them as query params", async () => {
    mockFetch.mockResolvedValue(okJson({ results: [] }));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await companiesHandler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/companies?limit=100&offset=0&user_id=current",
      {
        method: "GET",
        headers: { "Content-Type": "application/json", "x-user-id": "current" },
      },
    );
  });

  it("prefers query values and passes through the response", async () => {
    mockFetch.mockResolvedValue(okJson({ results: [{ name: "Acme" }] }));
    const { req, res } = createMocks({
      method: "GET",
      query: { limit: "5", offset: "10", user_id: "u1" },
    }) as any;
    await companiesHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/companies?limit=5&offset=10&user_id=u1",
      expect.anything(),
    );
    expect(res._getJSONData()).toEqual({ results: [{ name: "Acme" }] });
  });

  it("falls back to body values when query params are absent", async () => {
    mockFetch.mockResolvedValue(okJson({}));
    const { req, res } = createMocks({
      method: "GET",
      query: {},
      body: { limit: 3, offset: 7, user_id: "u2" },
    }) as any;
    await companiesHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/companies?limit=3&offset=7&user_id=u2",
      expect.anything(),
    );
  });

  it("returns 500 with message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await companiesHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch HubSpot companies",
      message: "down",
    });
  });
});

describe("pages/api/integrations/hubspot/contacts", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("forwards limit/offset/user_id defaults to the backend", async () => {
    mockFetch.mockResolvedValue(okJson({ results: [{ email: "a@b.c" }] }));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await contactsHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/contacts?limit=100&offset=0&user_id=current",
      expect.anything(),
    );
    expect(res._getJSONData()).toEqual({ results: [{ email: "a@b.c" }] });
  });

  it("uses query params when provided", async () => {
    mockFetch.mockResolvedValue(okJson({}));
    const { req, res } = createMocks({
      method: "GET",
      query: { limit: "2", offset: "1", user_id: "x" },
    }) as any;
    await contactsHandler(req, res);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hubspot/contacts?limit=2&offset=1&user_id=x",
      expect.anything(),
    );
  });

  it("mirrors backend error status", async () => {
    mockFetch.mockResolvedValue(errJson(500, { detail: "nope" }));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await contactsHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ detail: "nope" });
  });

  it("returns 500 with message when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await contactsHandler(req, res);
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      error: "Failed to fetch HubSpot contacts",
      message: "down",
    });
  });
});
