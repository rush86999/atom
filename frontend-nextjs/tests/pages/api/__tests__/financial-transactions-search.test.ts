import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/financial/transactions/search";

describe("pages/api/financial/transactions/search", () => {
  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 for non-POST methods", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData().error).toBe("Method not allowed");
  });

  it("requires a userId", async () => {
    const res = await invoke("POST", { query: "grocery" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("User ID required");
  });

  it("returns all transactions with correct summary when no filters are given", async () => {
    const res = await invoke("POST", { userId: "u-1" });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.transactions).toHaveLength(8);
    expect(body.summary.totalTransactions).toBe(8);
    expect(body.summary.totalSpent).toBeCloseTo(438.18);
    expect(body.summary.totalIncome).toBe(3850);
    expect(body.summary.netFlow).toBeCloseTo(3411.82);
    expect(body.summary.categories).toHaveLength(6);
    const dining = body.summary.categories.find(
      (c: any) => c.category === "Dining",
    );
    expect(dining.amount).toBeCloseTo(74.25);
    expect(dining.transactionCount).toBe(2);
  });

  it("filters by free-text query across name/description/category", async () => {
    const res = await invoke("POST", { userId: "u-1", query: "amazon" });
    const body = res._getJSONData();
    expect(body.transactions).toHaveLength(1);
    expect(body.transactions[0].id).toBe("txn_2");

    const res2 = await invoke("POST", { userId: "u-1", query: "DINING" });
    expect(res2._getJSONData().transactions).toHaveLength(2);
  });

  it("filters by category case-insensitively", async () => {
    const res = await invoke("POST", { userId: "u-1", category: "dining" });
    const body = res._getJSONData();
    expect(body.transactions.map((t: any) => t.id)).toEqual(["txn_3", "txn_7"]);
  });

  it("filters by date range inclusively", async () => {
    const res = await invoke("POST", {
      userId: "u-1",
      dateRange: { start: "2024-06-05", end: "2024-06-07" },
    });
    const body = res._getJSONData();
    expect(body.transactions.map((t: any) => t.id).sort()).toEqual([
      "txn_3",
      "txn_4",
      "txn_5",
      "txn_8",
    ]);
  });

  it("filters by absolute amount range", async () => {
    const res = await invoke("POST", {
      userId: "u-1",
      amountRange: { min: 50, max: 100 },
    });
    const body = res._getJSONData();
    expect(body.transactions.map((t: any) => t.id).sort()).toEqual([
      "txn_2",
      "txn_7",
      "txn_8",
    ]);
  });

  it("respects the limit and summarizes only returned transactions", async () => {
    const res = await invoke("POST", { userId: "u-1", limit: 2 });
    const body = res._getJSONData();
    expect(body.transactions).toHaveLength(2);
    expect(body.summary.totalTransactions).toBe(2);
    expect(body.summary.totalSpent).toBeCloseTo(127.45 + 89.99);
    expect(body.summary.categories).toHaveLength(2);
  });

  it("ignores incomplete date ranges", async () => {
    const res = await invoke("POST", {
      userId: "u-1",
      dateRange: { start: "2024-06-05" },
    });
    expect(res._getJSONData().transactions).toHaveLength(8);
  });

  it("returns 500 when the handler throws", async () => {
    const res = await invoke("POST", {
      userId: "u-1",
      query: { nested: "not a string" } as any,
    });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData().error).toBe("Failed to search transactions");
  });
});
