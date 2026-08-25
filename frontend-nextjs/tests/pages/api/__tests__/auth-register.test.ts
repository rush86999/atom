/**
 * pages/api/auth/register tests.
 *
 * The handler is a thin proxy to the Python backend (R83 rewrite):
 * - validates method, email/password presence, password policy (mirrors the
 *   backend's UserCreate rules), and requires a first name (last optional)
 * - passes backend status/error bodies through verbatim, including 429
 *   Retry-After headers
 * - returns 502 when the backend is unreachable (the old direct-Postgres
 *   fallback was removed — it wrote ghost rows the backend never reads)
 */

const mockFetch = jest.fn();
(global as any).fetch = mockFetch;

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/auth/register";

const okBody = { access_token: "tok", user: { id: "u1" } };

// Use real Response objects: the test-env fetch wrapper calls
// response.clone(), which plain object mocks don't implement.
const jsonResponse = (status: number, body: unknown, headers?: Record<string, string>) =>
  new Response(JSON.stringify(body), { status, headers });

describe("pages/api/auth/register", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 for non-POST methods", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData().error).toBe("Method not allowed");
  });

  it("returns 400 when email or password is missing", async () => {
    const res = await invoke("POST", { email: "a@b.com" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Email and password are required");
  });

  it("rejects passwords shorter than 8 characters", async () => {
    const res = await invoke("POST", { email: "a@b.com", password: "weak", first_name: "Jane" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Password must be at least 8 characters long");
  });

  it("requires a first name (last name optional)", async () => {
    const res = await invoke("POST", { email: "a@b.com", password: "Str0ng!Passw0rd" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("First name is required");
  });

  it("accepts a single full name and splits it", async () => {
    mockFetch.mockResolvedValue(jsonResponse(201, okBody));
    const res = await invoke("POST", { email: "a@b.com", password: "Str0ng!Passw0rd", name: "Jane Doe" });
    expect(res._getStatusCode()).toBe(201);
    // The test-env fetch interceptor hands the mock a single Request object
    // (url + init already merged), so read the body from it.
    const request = mockFetch.mock.calls[0][0] as Request;
    expect(request.url).toContain("/api/auth/register");
    const sent = await request.json();
    expect(sent.first_name).toBe("Jane");
    expect(sent.last_name).toBe("Doe");
  });

  it("proxies a successful registration and returns 201 with the body", async () => {
    mockFetch.mockResolvedValue(jsonResponse(201, okBody));
    const res = await invoke("POST", { email: "a@b.com", password: "Str0ng!Passw0rd", first_name: "Jane", last_name: "Doe" });
    expect(res._getStatusCode()).toBe(201);
    expect(res._getJSONData()).toEqual(okBody);
  });

  it("passes through a 400 from the backend verbatim", async () => {
    mockFetch.mockResolvedValue(jsonResponse(400, { error: "user exists" }));
    const res = await invoke("POST", { email: "a@b.com", password: "Str0ng!Passw0rd", first_name: "Jane" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "user exists" });
  });

  it("forwards Retry-After on backend 429 rate limits", async () => {
    mockFetch.mockResolvedValue(jsonResponse(429, { error: "rate_limited" }, { "Retry-After": "30" }));
    const res = await invoke("POST", { email: "a@b.com", password: "Str0ng!Passw0rd", first_name: "Jane" });
    expect(res._getStatusCode()).toBe(429);
    expect(res.getHeader("Retry-After")).toBe("30");
  });

  it("returns 502 when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("POST", { email: "a@b.com", password: "Str0ng!Passw0rd", first_name: "Jane" });
    expect(res._getStatusCode()).toBe(502);
    expect(res._getJSONData().error).toBe("Registration service is unreachable");
  });
});
