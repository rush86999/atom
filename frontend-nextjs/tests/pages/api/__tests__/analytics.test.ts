const mockRedisInstance = {
  get: jest.fn(),
  zcount: jest.fn(),
  smembers: jest.fn(),
};
jest.mock("ioredis", () => jest.fn(() => mockRedisInstance));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/analytics";

describe("pages/api/analytics", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRedisInstance.get.mockResolvedValue("0");
    mockRedisInstance.zcount.mockResolvedValue(0);
    mockRedisInstance.smembers.mockResolvedValue([]);
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  it("rejects non-GET with 405", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    expect(mockRedisInstance.get).not.toHaveBeenCalled();
  });

  it("generates analytics for the default 24h range", async () => {
    mockRedisInstance.get.mockResolvedValue("42");
    mockRedisInstance.zcount.mockResolvedValue(7);
    mockRedisInstance.smembers.mockResolvedValue(["slack", "github"]);
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.success).toBe(true);
    expect(body.timeRange).toBe("24h");
    expect(typeof body.generatedAt).toBe("string");
    expect(body.data.metrics.users).toEqual({ total: 42, active: 7, new: 7 });
    expect(body.data.metrics.integrations.total).toBe(42);
    expect(body.data.metrics.integrations.connected).toBe(2);
    expect(mockRedisInstance.zcount).toHaveBeenCalledWith(
      "analytics:users:active",
      expect.any(Number),
      "+inf",
    );
  });

  it("supports the 1h time range", async () => {
    const { req, res } = createMocks({ method: "GET", query: { timeRange: "1h" } }) as any;
    await handler(req, res);
    expect(res._getJSONData().timeRange).toBe("1h");
  });

  it("supports the 7d and 30d time ranges", async () => {
    for (const range of ["7d", "30d"]) {
      const { req, res } = createMocks({ method: "GET", query: { timeRange: range } }) as any;
      await handler(req, res);
      expect(res._getJSONData().timeRange).toBe(range);
    }
  });

  it("falls back to 24h for an unknown time range", async () => {
    const { req, res } = createMocks({ method: "GET", query: { timeRange: "5y" } }) as any;
    await handler(req, res);
    expect(res._getJSONData().timeRange).toBe("5y");
    expect(res._getJSONData().success).toBe(true);
  });

  it("returns a single usage entry when a service filter is provided", async () => {
    mockRedisInstance.get.mockImplementation((key: string) => {
      if (key === "analytics:integrations:slack:count") return Promise.resolve("12");
      if (key === "analytics:integrations:slack:lastUsed") return Promise.resolve(String(Date.now()));
      return Promise.resolve("3");
    });
    const { req, res } = createMocks({ method: "GET", query: { service: "slack" } }) as any;
    await handler(req, res);
    const usage = res._getJSONData().data.metrics.integrations.usage;
    expect(usage).toHaveLength(1);
    expect(usage[0].service).toBe("slack");
    expect(usage[0].count).toBe(12);
    expect(typeof usage[0].lastUsed).toBe("string");
  });

  it("collects usage across services and ranks by count", async () => {
    mockRedisInstance.get.mockImplementation((key: string) => {
      const m = key.match(/analytics:integrations:(\w+):count/);
      if (m) return Promise.resolve(m[1] === "slack" ? "9" : m[1] === "github" ? "4" : "0");
      if (key.endsWith(":lastUsed")) return Promise.resolve("1000");
      return Promise.resolve("0");
    });
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await handler(req, res);
    const usage = res._getJSONData().data.metrics.integrations.usage;
    expect(usage).toEqual([
      { service: "slack", count: 9, lastUsed: new Date(1000).toISOString() },
      { service: "github", count: 4, lastUsed: new Date(1000).toISOString() },
    ]);
  });

  it("computes the error rate from request counts", async () => {
    mockRedisInstance.get.mockImplementation((key: string) => {
      if (key === "analytics:performance:errors") return Promise.resolve("5");
      if (key === "analytics:performance:requests") return Promise.resolve("100");
      if (key === "analytics:performance:avgResponse") return Promise.resolve("120.5");
      if (key === "analytics:performance:throughput") return Promise.resolve("99");
      return Promise.resolve("0");
    });
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await handler(req, res);
    const perf = res._getJSONData().data.metrics.performance;
    expect(perf.averageResponseTime).toBe(120.5);
    expect(perf.throughput).toBe(99);
    expect(perf.errorRate).toBe(5);
    expect(perf.uptime).toEqual(expect.any(Number));
  });

  it("reports zero error rate when there are no requests", async () => {
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await handler(req, res);
    expect(res._getJSONData().data.metrics.performance.errorRate).toBe(0);
  });

  it("falls back to zero defaults when redis keys are missing", async () => {
    mockRedisInstance.get.mockResolvedValue(null);
    mockRedisInstance.zcount.mockResolvedValue(0);
    mockRedisInstance.smembers.mockResolvedValue([]);
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await handler(req, res);
    const metrics = res._getJSONData().data.metrics;
    expect(metrics.users.total).toBe(0);
    expect(metrics.integrations.total).toBe(0);
    expect(metrics.integrations.usage).toEqual([]);
    expect(metrics.performance.averageResponseTime).toBe(0);
    expect(metrics.performance.throughput).toBe(0);
  });

  it("applies the service fallback defaults when keys are missing", async () => {
    mockRedisInstance.get.mockResolvedValue(null);
    const { req, res } = createMocks({ method: "GET", query: { service: "slack" } }) as any;
    await handler(req, res);
    const usage = res._getJSONData().data.metrics.integrations.usage;
    expect(usage).toEqual([
      { service: "slack", count: 0, lastUsed: new Date(0).toISOString() },
    ]);
  });

  it("falls back to zeros when redis reads fail", async () => {
    mockRedisInstance.get.mockRejectedValue(new Error("redis down"));
    mockRedisInstance.zcount.mockRejectedValue(new Error("redis down"));
    mockRedisInstance.smembers.mockRejectedValue(new Error("redis down"));
    const { req, res } = createMocks({ method: "GET", query: {} }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const metrics = res._getJSONData().data.metrics;
    expect(metrics.users).toEqual({ total: 0, active: 0, new: 0 });
    expect(metrics.integrations).toEqual({ total: 0, connected: 0, usage: [] });
    expect(metrics.performance).toEqual({ averageResponseTime: 0, throughput: 0, errorRate: 0, uptime: 0 });
    expect(metrics.features).toEqual({ searchQueries: 0, workflowExecutions: 0, agentTasks: 0, aiInteractions: 0 });
  });
});
