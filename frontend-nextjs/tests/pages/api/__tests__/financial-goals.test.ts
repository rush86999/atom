import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/financial/goals";

describe("pages/api/financial/goals", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "GET", body: any = {}, query: any = {}) => {
    const { req, res } = createMocks({ method: method as RequestMethod, body, query }) as any;
    await handler(req, res);
    return res;
  };

  describe("GET", () => {
    it("returns 400 when userId is missing", async () => {
      const res = await invoke("GET", {}, {});
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({ error: "User ID required" });
    });

    it("returns all goals with summary when no goalType is given", async () => {
      const res = await invoke("GET", {}, { userId: "user-1" });
      expect(res._getStatusCode()).toBe(200);
      const body = res._getJSONData();
      expect(body.goals).toHaveLength(4);
      expect(body.summary.totalGoals).toBe(4);
      expect(body.summary.totalTarget).toBe(74000);
      expect(body.summary.totalSaved).toBe(19700);
      expect(body.summary.totalProgress).toBeCloseTo(26.62, 1);
    });

    it("filters goals by goalType and recomputes the summary", async () => {
      const res = await invoke("GET", {}, { userId: "user-1", goalType: "purchase" });
      expect(res._getStatusCode()).toBe(200);
      const body = res._getJSONData();
      expect(body.goals).toHaveLength(2);
      expect(body.goals.every((g: any) => g.goalType === "purchase")).toBe(true);
      expect(body.summary.totalTarget).toBe(58000);
      expect(body.summary.totalSaved).toBe(12000);
      expect(body.summary.totalProgress).toBeCloseTo(20.69, 1);
    });

    it("returns an empty goal list with a zero progress summary for unknown goalTypes", async () => {
      const res = await invoke("GET", {}, { userId: "user-1", goalType: "retirement" });
      expect(res._getStatusCode()).toBe(200);
      const body = res._getJSONData();
      expect(body.goals).toHaveLength(0);
      expect(body.summary.totalGoals).toBe(0);
      expect(body.summary.totalTarget).toBe(0);
      expect(body.summary.totalSaved).toBe(0);
      expect(body.summary.totalProgress).toBe(0);
    });
  });

  describe("POST", () => {
    it("returns 400 when required fields are missing", async () => {
      const res = await invoke("POST", { userId: "user-1", name: "Boat" });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData().error).toContain("Missing required fields");
    });

    it("returns 400 for an empty body", async () => {
      const res = await invoke("POST", {});
      expect(res._getStatusCode()).toBe(400);
    });

    it("creates a goal with computed progress and defaults", async () => {
      const res = await invoke("POST", {
        userId: "user-1",
        name: "New Car",
        targetAmount: 10000,
        goalType: "purchase",
        currentAmount: 2500,
      });
      expect(res._getStatusCode()).toBe(201);
      const { data } = res._getJSONData();
      expect(data.id).toMatch(/^goal_\d+$/);
      expect(data.name).toBe("New Car");
      expect(data.targetAmount).toBe(10000);
      expect(data.current).toBe(2500);
      expect(data.progress).toBe(25);
      expect(data.status).toBe("active");
      expect(data.priority).toBe(3);
      expect(data.description).toBe("");
      expect(new Date(data.createdAt).toISOString()).toBe(data.createdAt);
    });

    it("honors an explicit priority and description", async () => {
      const res = await invoke("POST", {
        userId: "user-1",
        name: "Emergency Fund",
        targetAmount: 5000,
        goalType: "emergency",
        priority: 1,
        description: "Safety net",
      });
      expect(res._getStatusCode()).toBe(201);
      const { data } = res._getJSONData();
      expect(data.priority).toBe(1);
      expect(data.description).toBe("Safety net");
    });
  });

  describe("PUT", () => {
    it("returns 400 when goalId or userId is missing", async () => {
      const res = await invoke("PUT", { userId: "user-1" });
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData().error).toBe("Goal ID and User ID required");
    });

    it("updates a goal and recomputes progress", async () => {
      const res = await invoke("PUT", {
        goalId: "goal_001",
        userId: "user-1",
        name: "Emergency Fund",
        targetAmount: 12000,
        currentAmount: 3000,
        targetDate: "2025-01-01",
      });
      expect(res._getStatusCode()).toBe(200);
      const { data } = res._getJSONData();
      expect(data.id).toBe("goal_001");
      expect(data.targetAmount).toBe(12000);
      expect(data.current).toBe(3000);
      expect(data.progress).toBe(25);
      expect(data.targetDate).toBe("2025-01-01");
    });

    it("returns progress 0 instead of NaN when targetAmount is omitted", async () => {
      const res = await invoke("PUT", {
        goalId: "goal_001",
        userId: "user-1",
        currentAmount: 3000,
      });
      expect(res._getStatusCode()).toBe(200);
      const { data } = res._getJSONData();
      expect(data.progress).toBe(0);
    });
  });

  it("returns 405 for unsupported methods", async () => {
    const res = await invoke("DELETE", {}, {});
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData().error).toBe("Method not allowed");
  });
});
