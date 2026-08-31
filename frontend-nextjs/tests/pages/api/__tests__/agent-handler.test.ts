import {
  getCurrentUserId,
  handleMessage,
  default as defaultHandler,
} from "@/pages/api/agent/handler";

function makeJwt(payload: object): string {
  const enc = Buffer.from(JSON.stringify(payload)).toString("base64");
  return `eyJhbGciOiJIUzI1NiJ9.${enc}.signature`;
}

describe("pages/api/agent/handler", () => {
  const originalNodeEnv = process.env.NODE_ENV;

  const clearGlobals = () => {
    delete (global as any).__postgraphileContext;
    delete (global as any).__postgraphile;
    delete (global as any).postgres;
  };

  beforeEach(() => {
    jest.clearAllMocks();
    clearGlobals();
    (process.env as any).NODE_ENV = "test";
  });

  afterAll(() => {
    (process.env as any).NODE_ENV = originalNodeEnv;
    clearGlobals();
  });

  describe("getCurrentUserId", () => {
    it("extracts user from Bearer JWT sub claim", () => {
      const id = getCurrentUserId({
        headers: { authorization: `Bearer ${makeJwt({ sub: "user-123" })}` },
      });
      expect(id).toBe("user-123");
    });

    it("falls back to user_id claim when sub is absent", () => {
      const id = getCurrentUserId({
        headers: { authorization: `Bearer ${makeJwt({ user_id: "u2" })}` },
      });
      expect(id).toBe("u2");
    });

    it("extracts session user from postgraphile-session cookie", () => {
      const id = getCurrentUserId({
        headers: { cookie: "postgraphile-session=abcdefgh1234" },
      });
      expect(id).toBe("_session_abcdefgh");
    });

    it("prefers authenticated user from global postgres context for cookie sessions", () => {
      (global as any).postgres = { authenticatedUserId: "pg-user-9" };
      const id = getCurrentUserId({
        headers: { cookie: "postgraphile-session=abcdefgh" },
      });
      expect(id).toBe("pg-user-9");
    });

    it("uses global PostGraphile RLS context when no request headers", () => {
      (global as any).__postgraphileContext = { jwtClaims: { sub: "rls-user" } };
      expect(getCurrentUserId()).toBe("rls-user");
    });

    it("returns test user when no request and NODE_ENV is test", () => {
      expect(getCurrentUserId()).toBe("test_user_from_postgraphile_db");
    });

    it("falls back to development user in development mode", () => {
      const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
      (process.env as any).NODE_ENV = "development";
      expect(getCurrentUserId()).toBe("dev_postgraphile_user_001");
      expect(warnSpy).toHaveBeenCalled();
      warnSpy.mockRestore();
    });

    it("returns dev user when a token is malformed outside production", () => {
      const id = getCurrentUserId({
        headers: { authorization: "Bearer not-a-valid-jwt" },
      });
      expect(id).toBe("dev_postgraphile_user_001");
    });

    it("returns global postgraphile userId in production", () => {
      (process.env as any).NODE_ENV = "production";
      (global as any).__postgraphile = { userId: "prod-user-5" };
      expect(getCurrentUserId()).toBe("prod-user-5");
    });

    it("throws in production when no authenticated user exists", () => {
      (process.env as any).NODE_ENV = "production";
      expect(() => getCurrentUserId()).toThrow(
        "User authentication required via PostGraphile JWT/session context",
      );
    });
  });

  describe("handleMessage", () => {
    it("echoes the message with settings", async () => {
      const response = await handleMessage("hello atom", { mode: "demo" });
      expect(response).toEqual({ text: "Echo: hello atom" });
    });
  });

  describe("default export", () => {
    it("is a no-op stub returning null", () => {
      expect(defaultHandler()).toBeNull();
    });
  });
});
