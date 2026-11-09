const mockGetToken = jest.fn();
const mockGetSession = jest.fn();
jest.mock("next-auth/jwt", () => ({ getToken: mockGetToken }));
jest.mock("next-auth/react", () => ({ getSession: mockGetSession }));

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/skills/list";

const mockFetch = jest.fn();
const environmentKeys = ['BACKEND_URL','API_BASE_URL','PYTHON_BACKEND_URL','BACKEND_API_URL','NEXT_PUBLIC_API_URL'];
const originalEnvironment = Object.fromEntries(environmentKeys.map(key => [key,process.env[key]]));

const jsonResponse = (body: any, status = 200) => ({
  ok: status < 400,
  status,
  headers: {
    get: (name: string) =>
      name.toLowerCase() === "content-type" ? "application/json" : null,
  },
  json: async () => body,
  text: async () => JSON.stringify(body),
});

const htmlResponse = (status = 502) => ({
  ok: false,
  status,
  headers: {
    get: (name: string) => (name.toLowerCase() === "content-type" ? "text/html" : null),
  },
  json: async () => { throw new SyntaxError('controlled non-JSON'); },
  text: async () => "<html>Service Unavailable</html>",
});

describe("pages/api/skills/list", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
    jest.spyOn(console, "warn").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    for (const key of environmentKeys) delete process.env[key];
    process.env.BACKEND_API_URL='http://127.0.0.1:8000';
    mockGetToken.mockResolvedValue(null);
    mockGetSession.mockResolvedValue(null);
    mockFetch.mockResolvedValue(
      jsonResponse({ success: true, data: { skills: [{ skill_id: "s1" }], total: 1 } }),
    );
  });

  afterEach(() => {
    for (const key of environmentKeys) { if (originalEnvironment[key] === undefined) delete process.env[key]; else process.env[key] = originalEnvironment[key]; }
  });

  const invoke = async (method: RequestMethod = "GET", query: any = {}) => {
    const { req, res } = createMocks({ method, query, headers: {authorization:'Bearer controlled-list-bearer'}, cookies:{} }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-GET methods with 405", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("proxies to the default backend URL and returns the skills payload", async () => {
    const res = await invoke();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      data: { skills: [{ skill_id: "s1" }], total: 1 },
    });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/skills/list",
    );
    expect(res.getHeader("Cache-Control")).toBe(
      "private, no-store",
    );
  });

  it("prefers BACKEND_API_URL when set", async () => {
    process.env.BACKEND_API_URL = "http://backend:9000";
    await invoke();
    expect(mockFetch.mock.calls[0][0]).toBe("http://backend:9000/api/skills/list");
  });

  it("sends the Authorization header when the JWT contains an access token", async () => {
    // Current cookie contract carries backendToken, never the encrypted container.
    mockGetToken.mockResolvedValue({ backendToken: 'token-from-jwt' });
    const {req,res}=createMocks({method:'GET',query:{},headers:{},cookies:{'next-auth.session-token':'controlled-cookie'}}) as any;
    await handler(req,res);
    expect(mockFetch.mock.calls[0][1].headers.Authorization).toBe('Bearer token-from-jwt');
  });

  it("falls back to the session access token", async () => {
    // Obsolete client session fields cannot lend authority to an unauthenticated call.
    mockGetSession.mockResolvedValue({ accessToken: 'token-from-session' });
    const {req,res}=createMocks({method:'GET',query:{},headers:{},cookies:{}}) as any;
    await handler(req,res);
    expect(res._getStatusCode()).toBe(401);
    expect(mockGetSession).not.toHaveBeenCalled();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("omits the Authorization header when no access token exists", async () => {
    const {req,res}=createMocks({method:'GET',query:{},headers:{},cookies:{}}) as any;
    await handler(req,res);
    expect(res._getStatusCode()).toBe(401);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("forwards query parameters to the backend", async () => {
    await invoke("GET", { status: "active", skill_type: "custom" });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/skills/list?status=active&skill_type=custom",
    );
  });

  it("rejects non-JSON backend responses with the upstream status", async () => {
    mockFetch.mockResolvedValue(htmlResponse(502));
    const res=await invoke();
    // Unknown body is a safe transport failure, never raw diagnostics.
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData().code).toBe('BACKEND_UNAVAILABLE');
    expect(JSON.stringify(res._getJSONData())).not.toContain('<html>');
  });

  it("returns an empty list when the backend replies non-OK JSON", async () => {
    mockFetch.mockResolvedValue(jsonResponse({error:'boom'},500));
    const res=await invoke();
    // Historical false-success case retained as a negative twin.
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({error:'boom'});
  });

  it("returns an empty list when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error('PRIVATE_CONNECTION_DIAGNOSTIC'));
    const res=await invoke();
    expect(res._getStatusCode()).toBe(503);
    expect(res._getJSONData().code).toBe('BACKEND_UNAVAILABLE');
    expect(JSON.stringify(res._getJSONData())).not.toContain('PRIVATE_CONNECTION_DIAGNOSTIC');
  });

  it('preserves a genuine empty successful result',async()=>{
    const empty={success:true,data:{skills:[],total:0}};
    mockFetch.mockResolvedValue(jsonResponse(empty));
    const res=await invoke();expect(res._getStatusCode()).toBe(200);expect(res._getJSONData()).toEqual(empty);
  });

  it.each([null,{success:false,data:{skills:[],total:0}},{success:true,data:{skills:[],total:1}},{success:true,data:{skills:[{}],total:1}}])('refuses malformed success material %j',async payload=>{
    mockFetch.mockResolvedValue(jsonResponse(payload));const res=await invoke();expect(res._getStatusCode()).toBe(502);expect(res._getJSONData().success).toBe(false);
  });
});
