const mockQuery = jest.fn();
jest.mock("@/lib/db", () => ({ query: mockQuery }));

jest.mock("next-auth", () => ({
  __esModule: true,
  default: jest.fn(),
  getServerSession: jest.fn(),
}));

import { authOptions } from "@/pages/api/auth/[...nextauth]";

function jsonResponse(ok: boolean, body: any, contentType = "application/json") {
  return {
    ok,
    headers: { get: () => contentType },
    text: async () => "plain body",
    json: async () => body,
  } as any;
}

const credentialsProvider: any = authOptions.providers.find(
  (p: any) => p.id === "credentials",
);

describe("pages/api/auth/[...nextauth] authorize (extra branches)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("falls back to data.id and email-prefix name", async () => {
    (global as any).fetch = jest.fn().mockResolvedValue(
      jsonResponse(true, { access_token: "at", id: "plain-id" }),
    );
    const result = await credentialsProvider.options.authorize(
      { email: "some.user@example.com", password: "x" },
      {} as any,
    );
    expect(result).toEqual({
      id: "plain-id",
      email: "some.user@example.com",
      name: "some.user",
      token: "at",
    });
  });

  it("falls back to 'user-from-backend' id and 'Atom User' name", async () => {
    (global as any).fetch = jest.fn().mockResolvedValue(
      jsonResponse(true, { access_token: "at", user: {} }),
    );
    const result = await credentialsProvider.options.authorize(
      { email: "", password: "x" },
      {} as any,
    );
    expect(result).toEqual({
      id: "user-from-backend",
      email: "",
      name: "Atom User",
      token: "at",
    });
  });

  it("handles missing credentials", async () => {
    (global as any).fetch = jest.fn().mockResolvedValue(
      jsonResponse(true, { access_token: "at", user: { id: "u", name: "N" } }),
    );
    const result = await credentialsProvider.options.authorize(undefined, {} as any);
    expect(result).toEqual({ id: "u", email: undefined, name: "N", token: "at" });
    expect((global as any).fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/auth\/login$/),
      expect.objectContaining({
        body: JSON.stringify({ username: "", password: "" }),
      }),
    );
  });

  it("strips a trailing slash from the backend URL", async () => {
    const old = process.env.NEXT_PUBLIC_API_URL;
    process.env.NEXT_PUBLIC_API_URL = "http://api.example.com:8000/";
    (global as any).fetch = jest.fn().mockResolvedValue(
      jsonResponse(true, { access_token: "at", user: { id: "u", name: "N" } }),
    );
    await credentialsProvider.options.authorize(
      { email: "a@b.com", password: "x" },
      {} as any,
    );
    expect((global as any).fetch).toHaveBeenCalledWith(
      "http://api.example.com:8000/api/auth/login",
      expect.anything(),
    );
    if (old === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = old;
  });
});

describe("pages/api/auth/[...nextauth] signIn (extra branches)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  const account = (overrides: any = {}) => ({
    provider: "google",
    providerAccountId: "ga-1",
    access_token: "at",
    refresh_token: "rt",
    expires_at: 1700000000,
    token_type: "Bearer",
    scope: "email profile",
    id_token: "it",
    ...overrides,
  });

  it("handles a github provider sign-in", async () => {
    mockQuery
      .mockResolvedValueOnce({ rows: [{ id: "db-1" }] })
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [] });
    const result = await authOptions.callbacks!.signIn!({
      user: { email: "gh@example.com", name: "GH", image: null },
      account: account({ provider: "github" }),
      profile: {} as any,
    } as any);
    expect(result).toBe(true);
    expect(mockQuery.mock.calls[2][0]).toContain("INSERT INTO user_accounts");
  });

  it("stores null when OAuth tokens are missing", async () => {
    mockQuery
      .mockResolvedValueOnce({ rows: [{ id: "db-1" }] })
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [] });
    const result = await authOptions.callbacks!.signIn!({
      user: { email: "x@example.com", name: "X", image: null },
      account: account({ access_token: null, refresh_token: null, id_token: null, expires_at: null }),
      profile: {} as any,
    } as any);
    expect(result).toBe(true);
    expect(mockQuery.mock.calls[2][1]).toEqual([
      "db-1",
      "google",
      "ga-1",
      null,
      null,
      null,
      "Bearer",
      "email profile",
      null,
    ]);
  });

  it("uses a string encryption key when OAUTH_TOKEN_ENCRYPTION_KEY is set", async () => {
    const old = process.env.OAUTH_TOKEN_ENCRYPTION_KEY;
    process.env.OAUTH_TOKEN_ENCRYPTION_KEY = "short-key";
    mockQuery
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [{ id: "db-2" }] })
      .mockResolvedValueOnce({ rows: [] });
    const result = await authOptions.callbacks!.signIn!({
      user: { email: "enc@example.com", name: "Enc", image: null },
      account: account(),
      profile: {} as any,
    } as any);
    expect(result).toBe(true);
    const upsertParams = mockQuery.mock.calls[2][1] as any[];
    expect(upsertParams[3]).toMatch(/^[0-9a-f]+:[0-9a-f]+:/);
    if (old === undefined) delete process.env.OAUTH_TOKEN_ENCRYPTION_KEY;
    else process.env.OAUTH_TOKEN_ENCRYPTION_KEY = old;
  });

  it("falls back to null when token encryption fails", async () => {
    jest
      .spyOn(require("crypto"), "randomBytes")
      .mockImplementation(() => {
        throw new Error("no entropy");
      });
    mockQuery
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [{ id: "db-3" }] })
      .mockResolvedValueOnce({ rows: [] });
    const result = await authOptions.callbacks!.signIn!({
      user: { email: "fail@example.com", name: "F", image: null },
      account: account(),
      profile: {} as any,
    } as any);
    expect(result).toBe(true);
    const upsertParams = mockQuery.mock.calls[2][1] as any[];
    expect(upsertParams[3]).toBeNull();
    jest.restoreAllMocks();
  });
});

describe("pages/api/auth/[...nextauth] jwt/session (extra branches)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    jest.spyOn(console, "log").mockImplementation(() => {});
    jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("uses user.backendToken when user.token is absent", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const token = (await authOptions.callbacks!.jwt!({
      token: {},
      user: { id: "u-1", email: "e@x.com", backendToken: "bt" } as any,
      account: {} as any,
      profile: {} as any,
      isNewUser: false,
    } as any)) as any;
    expect(token.backendToken).toBe("bt");
  });

  it("tolerates last-login database failures", async () => {
    mockQuery.mockRejectedValue(new Error("db down"));
    const token = await authOptions.callbacks!.jwt!({
      token: {},
      user: { id: "u-2", email: "e@x.com", token: "t" } as any,
      account: {} as any,
      profile: {} as any,
      isNewUser: false,
    } as any);
    expect(token.id).toBe("u-2");
    expect(console.error).toHaveBeenCalled();
  });

  it("returns the session unchanged when there is no token", async () => {
    const session = await authOptions.callbacks!.session!({
      session: { user: {} },
      token: undefined,
    } as any);
    expect(session).toEqual({ user: {} });
  });
});
