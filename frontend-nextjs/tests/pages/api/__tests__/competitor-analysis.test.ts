const mockGetServerSession = jest.fn();

jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/projects/competitor-analysis";

const mockFetch = jest.fn();
const mockSession = {
  user: { id: "user-1", email: "user@example.com" },
};

function backendJson(body: any, ok = true, status = 200): any {
  return { ok, status, json: async () => body };
}

describe("pages/api/projects/competitor-analysis", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "POST", body: any = {}, session: any = mockSession) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405 and an Allow header", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData().message).toContain("Method GET Not Allowed");
    expect(res.getHeader("Allow")).toEqual(["POST"]);
  });

  it("returns 401 without a session", async () => {
    const res = await invoke("POST", { competitors: ["Acme"] }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 400 when competitors is missing or empty", async () => {
    const res = await invoke("POST", {});
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe(
      "At least one competitor must be specified",
    );
  });

  it("returns 400 when more than 10 competitors are provided", async () => {
    const res = await invoke("POST", {
      competitors: Array.from({ length: 11 }, (_, i) => `c${i}`),
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe(
      "Maximum 10 competitors allowed per analysis",
    );
  });

  it("returns 400 for an invalid analysis depth", async () => {
    const res = await invoke("POST", {
      competitors: ["Acme"],
      analysis_depth: "ultra",
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toContain("Invalid analysis depth");
  });

  it("forwards the request with defaults and returns mapped success data", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        analysis_id: "an-1",
        status: "completed",
        insights: [{ competitor: "Acme", summary: "…" }],
        comparison_matrix: { rows: [] },
        recommendations: ["Do X"],
        created_at: "2026-08-01T00:00:00.000Z",
      }),
    );
    const res = await invoke("POST", {
      competitors: ["Acme", "Globex"],
      notionDatabaseId: "db-9",
    });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.analysis_id).toBe("an-1");
    expect(body.status).toBe("completed");
    expect(body.insights).toHaveLength(1);
    expect(body.comparison_matrix).toEqual({ rows: [] });
    expect(body.recommendations).toEqual(["Do X"]);
    expect(body.message).toBe("Competitor analysis completed successfully");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analysis/competitors",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "X-User-ID": "user-1",
        }),
      }),
    );
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      competitors: ["Acme", "Globex"],
      analysis_depth: "standard",
      focus_areas: ["products", "pricing", "marketing", "strengths", "weaknesses"],
      notion_database_id: "db-9",
    });
  });

  it("maps a backend 400 into a client 400 with detail", async () => {
    mockFetch.mockResolvedValue(
      backendJson({ detail: "No scraper available" }, false, 400),
    );
    const res = await invoke("POST", { competitors: ["Acme"] });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      message: "No scraper available",
      errors: ["No scraper available"],
    });
  });

  it("maps a backend 500 into a client 500", async () => {
    mockFetch.mockResolvedValue(
      backendJson({ message: "LLM quota exceeded" }, false, 500),
    );
    const res = await invoke("POST", { competitors: ["Acme"] });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().message).toBe("LLM quota exceeded");
  });

  it("returns 500 with the error message when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { competitors: ["Acme"] });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Failed to run competitor analysis",
      errors: ["ECONNREFUSED"],
    });
  });
});
