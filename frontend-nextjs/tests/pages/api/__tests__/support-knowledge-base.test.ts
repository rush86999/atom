import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/support/knowledge-base";

// The handler responds asynchronously via a 1-second setTimeout, so the tests
// advance fake timers before asserting on the response.
describe("pages/api/support/knowledge-base", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const invoke = (query: any = {}) => {
    const { req, res } = createMocks({ method: "GET", query }) as any;
    handler(req, res);
    jest.advanceTimersByTime(1000);
    return res;
  };

  it("returns all articles when no query is provided", () => {
    const res = invoke();
    expect(res._getStatusCode()).toBe(200);
    const data = res._getJSONData();
    expect(data).toHaveLength(6);
    expect(data[0]).toMatchObject({ id: "kb-1", category: "IT" });
  });

  it("returns all articles when the query is not a string", () => {
    const res = invoke({ q: ["vpn", "expenses"] });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toHaveLength(6);
  });

  it("filters articles by title (case-insensitive)", () => {
    const res = invoke({ q: "eXpense" });
    expect(res._getStatusCode()).toBe(200);
    const data = res._getJSONData();
    expect(data).toHaveLength(1);
    expect(data[0].id).toBe("kb-2");
  });

  it("filters articles by content match", () => {
    const res = invoke({ q: "workday" });
    expect(res._getStatusCode()).toBe(200);
    const data = res._getJSONData();
    expect(data).toHaveLength(1);
    expect(data[0].id).toBe("kb-3");
  });

  it("matches articles in both title and content for the same query", () => {
    // "vpn" appears in the kb-1 title and in the kb-5 content.
    const res = invoke({ q: "vpn" });
    expect(res._getJSONData().map((a: any) => a.id)).toEqual(["kb-1", "kb-5"]);
  });

  it("returns an empty array when nothing matches", () => {
    const res = invoke({ q: "quantum-teleportation" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual([]);
  });

  it("returns an empty array for an empty-string query", () => {
    // An empty string is falsy, so all articles are returned instead.
    const res = invoke({ q: "" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toHaveLength(6);
  });
});
