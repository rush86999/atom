const mockGetServerSession = jest.fn();
jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));

jest.mock("@/pages/api/auth/[...nextauth]", () => ({
  authOptions: { providers: [] },
}));

const mockExecuteGraphQLMutation = jest.fn();
const mockExecuteGraphQLQuery = jest.fn();
jest.mock("@/lib/graphqlClient", () => ({
  executeGraphQLMutation: mockExecuteGraphQLMutation,
  executeGraphQLQuery: mockExecuteGraphQLQuery,
}));

const mockEncrypt = jest.fn((t: string) => `enc:${t}`);
const mockDecrypt = jest.fn((t: string) => `dec:${t}`);
jest.mock("@/lib/crypto", () => ({
  encrypt: mockEncrypt,
  decrypt: mockDecrypt,
}));

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/integrations/credentials";

const mockSession = { user: { id: "user-1", email: "u@example.com" } };

describe("pages/api/integrations/credentials", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetServerSession.mockResolvedValue(mockSession);
    mockEncrypt.mockImplementation((t: string) => `enc:${t}`);
    mockDecrypt.mockImplementation((t: string) => `dec:${t}`);
    mockExecuteGraphQLMutation.mockResolvedValue({});
    mockExecuteGraphQLQuery.mockResolvedValue({ data: {} });
  });

  const invoke = async (
    method: string,
    opts: { body?: any; query?: any; session?: any } = {},
  ) => {
    mockGetServerSession.mockResolvedValue(
      opts.session === undefined ? mockSession : opts.session,
    );
    const { req, res } = createMocks({ method: method as RequestMethod, ...opts }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 401 when there is no session", async () => {
    const res = await invoke("GET", { query: { service: "linear" }, session: null });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 401 when the session has no user", async () => {
    const res = await invoke("GET", { query: { service: "linear" }, session: {} });
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  describe("POST", () => {
    it("rejects non-POST/GET methods with 405 and Allow header", async () => {
      const res = await invoke("DELETE");
      expect(res._getStatusCode()).toBe(405);
      expect(res._getData()).toContain("Method DELETE Not Allowed");
      expect(res.getHeader("Allow")).toEqual(["POST", "GET"]);
    });

    it("returns 400 when service is missing", async () => {
      const res = await invoke("POST", { body: { secret: "s" } });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({
        message: "Service and secret are required",
      });
    });

    it("returns 400 when secret is missing", async () => {
      const res = await invoke("POST", { body: { service: "linear" } });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({
        message: "Service and secret are required",
      });
    });

    it("encrypts the secret and saves the credential", async () => {
      const res = await invoke("POST", {
        body: { service: "linear", secret: "sk-123" },
      });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({
        message: "linear credentials saved successfully",
      });
      expect(mockEncrypt).toHaveBeenCalledWith("sk-123");
      expect(mockExecuteGraphQLMutation).toHaveBeenCalledWith(
        expect.stringContaining("SaveCredential"),
        { userId: "user-1", service: "linear", secret: "enc:sk-123" },
      );
    });

    it("returns 500 when the mutation fails", async () => {
      mockExecuteGraphQLMutation.mockRejectedValue(new Error("gql down"));
      const res = await invoke("POST", {
        body: { service: "linear", secret: "sk-123" },
      });
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        message: "Failed to save linear credentials",
      });
      expect(console.error).toHaveBeenCalled();
    });
  });

  describe("GET", () => {
    it("returns 400 when service is missing", async () => {
      const res = await invoke("GET", { query: {} });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({ message: "Service is required" });
    });

    it("reports connected with the decrypted secret when a credential exists", async () => {
      mockExecuteGraphQLQuery.mockResolvedValue({
        data: {
          user_credentials_by_pk: { encrypted_secret: "enc-stored" },
        },
      });
      const res = await invoke("GET", { query: { service: "linear" } });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({
        isConnected: true,
        value: "dec:enc-stored",
      });
      expect(mockDecrypt).toHaveBeenCalledWith("enc-stored");
      expect(mockExecuteGraphQLQuery).toHaveBeenCalledWith(
        expect.stringContaining("GetCredential"),
        { userId: "user-1", service: "linear" },
      );
    });

    it("reports not connected when no credential row exists", async () => {
      mockExecuteGraphQLQuery.mockResolvedValue({
        data: { user_credentials_by_pk: null },
      });
      const res = await invoke("GET", { query: { service: "linear" } });
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ isConnected: false });
    });

    it("reports not connected when the row has no secret", async () => {
      mockExecuteGraphQLQuery.mockResolvedValue({
        data: {
          user_credentials_by_pk: { encrypted_secret: null },
        },
      });
      const res = await invoke("GET", { query: { service: "linear" } });
      expect(res._getJSONData()).toEqual({ isConnected: false });
    });

    it("returns 500 when the query fails", async () => {
      mockExecuteGraphQLQuery.mockRejectedValue(new Error("gql down"));
      const res = await invoke("GET", { query: { service: "linear" } });
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        message: "Failed to check linear credentials",
      });
      expect(console.error).toHaveBeenCalled();
    });
  });
});
