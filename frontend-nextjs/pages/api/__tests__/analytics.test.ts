const mockRedisMethods = {
  get: jest.fn(),
  zcount: jest.fn(),
  smembers: jest.fn(),
};

jest.mock("ioredis", () =>
  jest.fn().mockImplementation(() => mockRedisMethods)
);

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/analytics";

describe("pages/api/analytics", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRedisMethods.get.mockResolvedValue("0");
    mockRedisMethods.zcount.mockResolvedValue(0);
    mockRedisMethods.smembers.mockResolvedValue([]);
  });

  const invoke = async (method = "GET", query: any = {}) => {
    const { req, res } = createMocks({ method, query }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 for non-GET methods", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("returns success with zeroed metrics when no data exists", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.success).toBe(true);
    expect(body.timeRange).toBe("24h");
    expect(body.generatedAt).toBeDefined();
    expect(body.data.timestamp).toBeDefined();
    expect(body.data.metrics.users).toEqual({ total: 0, active: 0, new: 0 });
    expect(body.data.metrics.integrations).toEqual({
      total: 0,
      connected: 0,
      usage: [],
    });
    expect(body.data.metrics.features).toEqual({
      searchQueries: 0,
      workflowExecutions: 0,
      agentTasks: 0,
      aiInteractions: 0,
    });
    expect(body.data.metrics.performance.errorRate).toBe(0);
    expect(typeof body.data.metrics.performance.uptime).toBe("number");
  });

  it("scopes time-based queries to the requested timeRange", async () => {
    mockRedisMethods.zcount.mockResolvedValue(5);
    const res = await invoke("GET", { timeRange: "7d" });
    expect(res._getStatusCode()).toBe(200);
    const calls = mockRedisMethods.zcount.mock.calls as any[];
    expect(calls.length).toBeGreaterThan(0);
    const expectedStart = (Date.now() - 7 * 24 * 60 * 60 * 1000) / 1000;
    for (const [key, start] of calls) {
      expect(key).toMatch(/^analytics:/);
      expect(Math.abs(start - expectedStart)).toBeLessThan(5);
    }
  });

  it("defaults an invalid timeRange to 24h", async () => {
    const res = await invoke("GET", { timeRange: "bogus" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().timeRange).toBe("bogus");
    const start = (mockRedisMethods.zcount.mock.calls as any)[0][1];
    const expectedStart = (Date.now() - 24 * 60 * 60 * 1000) / 1000;
    expect(Math.abs(start - expectedStart)).toBeLessThan(5);
  });

  it("returns per-service usage when service query param is provided", async () => {
    mockRedisMethods.get.mockImplementation((key: string) => {
      if (key === "analytics:integrations:slack:count") return Promise.resolve("42");
      if (key === "analytics:integrations:slack:lastUsed")
        return Promise.resolve("1700000000000");
      return Promise.resolve("0");
    });
    const res = await invoke("GET", { service: "slack" });
    expect(res._getStatusCode()).toBe(200);
    const usage = res._getJSONData().data.metrics.integrations.usage;
    expect(usage).toEqual([
      {
        service: "slack",
        count: 42,
        lastUsed: new Date(1700000000000).toISOString(),
      },
    ]);
  });

  it("aggregates usage across services, sorted desc, top 10, only non-zero", async () => {
    mockRedisMethods.smembers.mockResolvedValue(["slack", "github"]);
    mockRedisMethods.get.mockImplementation((key: string) => {
      if (key === "analytics:integrations:total") return Promise.resolve("7");
      if (key === "analytics:integrations:github:count") return Promise.resolve("15");
      if (key === "analytics:integrations:slack:count") return Promise.resolve("5");
      if (key === "analytics:integrations:slack:lastUsed")
        return Promise.resolve("1700000000000");
      return Promise.resolve("0");
    });
    const res = await invoke("GET");
    const integrations = res._getJSONData().data.metrics.integrations;
    expect(integrations.total).toBe(7);
    expect(integrations.connected).toBe(2);
    expect(integrations.usage.map((u: any) => u.service)).toEqual([
      "github",
      "slack",
    ]);
    expect(integrations.usage[0].count).toBe(15);
  });

  it("computes error rate from stored counters", async () => {
    mockRedisMethods.get.mockImplementation((key: string) => {
      if (key === "analytics:performance:avgResponse") return Promise.resolve("123.45");
      if (key === "analytics:performance:throughput") return Promise.resolve("100");
      if (key === "analytics:performance:errors") return Promise.resolve("5");
      if (key === "analytics:performance:requests") return Promise.resolve("100");
      return Promise.resolve("0");
    });
    const res = await invoke("GET");
    const perf = res._getJSONData().data.metrics.performance;
    expect(perf.averageResponseTime).toBe(123.45);
    expect(perf.throughput).toBe(100);
    expect(perf.errorRate).toBe(5);
  });

  it("degrades to zeroed metrics when redis calls fail", async () => {
    mockRedisMethods.get.mockRejectedValue(new Error("redis down"));
    mockRedisMethods.zcount.mockRejectedValue(new Error("redis down"));
    mockRedisMethods.smembers.mockRejectedValue(new Error("redis down"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.success).toBe(true);
    expect(body.data.metrics.users).toEqual({ total: 0, active: 0, new: 0 });
    expect(body.data.metrics.integrations.usage).toEqual([]);
    expect(body.data.metrics.features.searchQueries).toBe(0);
  });
});
