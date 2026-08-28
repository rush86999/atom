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

describe("pages/api/auth/[...nextauth] authOptions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("config shape", () => {
    it("defines Google, GitHub, and Credentials providers", () => {
      expect(authOptions.providers.map((p: any) => p.id)).toEqual([
        "google",
        "github",
        "credentials",
      ]);
    });

    it("configures JWT sessions with a 1-day max age", () => {
      expect(authOptions.session).toEqual({
        strategy: "jwt",
        maxAge: 24 * 60 * 60,
        updateAge: 60 * 60,
      });
    });

    it("configures pages and non-secure cookies outside production", () => {
      expect(authOptions.pages).toEqual({
        signIn: "/auth/signin",
        error: "/auth/error",
      });
      expect(authOptions.useSecureCookies).toBe(false);
      expect((authOptions.cookies as any).sessionToken.name).toBe(
        "next-auth.session-token",
      );
      expect((authOptions.cookies as any).csrfToken.name).toBe(
        "next-auth.csrf-token",
      );
      expect(authOptions.secret).toBeDefined();
    });
  });

  describe("credentials authorize", () => {
    const credentialsProvider: any = authOptions.providers.find(
      (p: any) => p.id === "credentials",
    );

    it("returns a user with backend token on successful login", async () => {
      (global as any).fetch = jest
        .fn()
        .mockResolvedValue(
          jsonResponse(true, {
            access_token: "at-123",
            user: { id: "u-1", name: "Alice Smith" },
          }),
        );
      const result = await credentialsProvider.options.authorize(
        { email: "alice@example.com", password: "secret" },
        {} as any,
      );
      expect(result).toEqual({
        id: "u-1",
        email: "alice@example.com",
        name: "Alice Smith",
        token: "at-123",
      });
      expect((global as any).fetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/auth\/login$/),
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("builds a name from first/last name claims when name is missing", async () => {
      (global as any).fetch = jest
        .fn()
        .mockResolvedValue(
          jsonResponse(true, {
            access_token: "at",
            user: { id: "u-2", first_name: "Bob", last_name: "Jones" },
          }),
        );
      const result = await credentialsProvider.options.authorize(
        { email: "bob@example.com", password: "x" },
        {} as any,
      );
      expect(result?.name).toBe("Bob Jones");
    });

    it("returns null when the backend responds with non-JSON", async () => {
      (global as any).fetch = jest
        .fn()
        .mockResolvedValue(jsonResponse(true, {}, "text/html"));
      const result = await credentialsProvider.options.authorize(
        { email: "a@b.com", password: "x" },
        {} as any,
      );
      expect(result).toBeNull();
    });

    it("returns null when login fails", async () => {
      (global as any).fetch = jest
        .fn()
        .mockResolvedValue(jsonResponse(false, { detail: "bad creds" }));
      const result = await credentialsProvider.options.authorize(
        { email: "a@b.com", password: "wrong" },
        {} as any,
      );
      expect(result).toBeNull();
    });

    it("returns null when the backend request throws", async () => {
      (global as any).fetch = jest
        .fn()
        .mockRejectedValue(new Error("network down"));
      const result = await credentialsProvider.options.authorize(
        { email: "a@b.com", password: "x" },
        {} as any,
      );
      expect(result).toBeNull();
    });
  });

  describe("signIn callback", () => {
    const googleAccount = {
      provider: "google",
      providerAccountId: "ga-1",
      access_token: "at",
      refresh_token: "rt",
      expires_at: 1700000000,
      token_type: "Bearer",
      scope: "email profile",
      id_token: "it",
    };

    it("creates a new user on first OAuth sign-in and stores the account", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [] }) // existing user check
        .mockResolvedValueOnce({ rows: [{ id: "db-42" }] }) // insert
        .mockResolvedValueOnce({ rows: [] }); // upsert account
      const result = await authOptions.callbacks!.signIn!({
        user: { email: "oauth@example.com", name: "OAuth User", image: "img" },
        account: googleAccount,
        profile: {} as any,
      } as any);
      expect(result).toBe(true);
      expect(mockQuery.mock.calls[1][0]).toContain("INSERT INTO users");
      expect(mockQuery.mock.calls[1][1]).toEqual([
        "oauth@example.com",
        "OAuth User",
        "img",
        "",
      ]);
      expect(mockQuery.mock.calls[2][0]).toContain("INSERT INTO user_accounts");
    });

    it("updates an existing user and their OAuth account", async () => {
      mockQuery
        .mockResolvedValueOnce({ rows: [{ id: "db-7" }] }) // existing user check
        .mockResolvedValueOnce({ rows: [] }) // update user
        .mockResolvedValueOnce({ rows: [] }); // upsert account
      const result = await authOptions.callbacks!.signIn!({
        user: { email: "existing@example.com", name: "Existing", image: null },
        account: googleAccount,
        profile: {} as any,
      } as any);
      expect(result).toBe(true);
      expect(mockQuery.mock.calls[1][0]).toContain("UPDATE users SET");
    });

    it("denies sign-in when the database write fails", async () => {
      mockQuery.mockRejectedValue(new Error("db exploded"));
      const result = await authOptions.callbacks!.signIn!({
        user: { email: "fail@example.com", name: "Fail" },
        account: googleAccount,
        profile: {} as any,
      } as any);
      expect(result).toBe(false);
    });

    it("allows non-OAuth (credentials) sign-ins without touching the DB", async () => {
      const result = await authOptions.callbacks!.signIn!({
        user: { email: "cred@example.com", name: "Cred" },
        account: { provider: "credentials" },
        profile: {} as any,
      } as any);
      expect(result).toBe(true);
      expect(mockQuery).not.toHaveBeenCalled();
    });
  });

  describe("jwt callback", () => {
    it("copies user fields into the token and records last login", async () => {
      mockQuery.mockResolvedValue({ rows: [] });
      const token = (await authOptions.callbacks!.jwt!({
        token: {},
        user: { id: "u-9", email: "e@x.com", token: "backend-tok" } as any,
        account: {} as any,
        profile: {} as any,
        isNewUser: true,
      } as any)) as any;
      expect(token.id).toBe("u-9");
      expect(token.email).toBe("e@x.com");
      expect(token.backendToken).toBe("backend-tok");
      expect(mockQuery).toHaveBeenCalledWith(
        expect.stringContaining("UPDATE users SET last_login_at"),
        ["u-9"],
      );
    });

    it("passes the token through unchanged when no user is present", async () => {
      const token = await authOptions.callbacks!.jwt!({
        token: { id: "existing" },
        user: undefined,
        account: undefined,
        profile: undefined,
        isNewUser: false,
        trigger: "update",
      } as any);
      expect(token).toEqual({ id: "existing" });
      expect(mockQuery).not.toHaveBeenCalled();
    });
  });

  describe("session callback", () => {
    it("populates session user from token claims", async () => {
      const session = await authOptions.callbacks!.session!({
        session: { user: { id: "", email: "" } },
        token: { id: "tok-id", email: "tok@x.com", backendToken: "bt" } as any,
      } as any);
      expect((session.user as any).id).toBe("tok-id");
      expect(session.user.email).toBe("tok@x.com");
      expect((session as any).backendToken).toBe("bt");
    });
  });
});
