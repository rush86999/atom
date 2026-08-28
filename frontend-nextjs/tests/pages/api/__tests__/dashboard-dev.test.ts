const mockFetch = jest.fn();

import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/dashboard-dev";

function backendJson(body: any, ok = true): any {
  return { ok, json: async () => body };
}

describe("pages/api/dashboard-dev", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "GET") => {
    const { req, res } = createMocks({ method: method as RequestMethod }) as any;
    await handler(req, res);
    return res;
  };

  it("responds to OPTIONS preflight with CORS headers and empty body", async () => {
    const res = await invoke("OPTIONS");
    expect(res._getStatusCode()).toBe(200);
    expect(res._getData()).toBe("");
    expect(res.getHeader("Access-Control-Allow-Origin")).toBe("*");
    expect(res.getHeader("Access-Control-Allow-Methods")).toContain("GET");
    expect(res.getHeader("Access-Control-Allow-Headers")).toContain(
      "Content-Type",
    );
  });

  it("returns mock fallback data instead of a 500 when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.calendar[0].id).toBe("mock-1");
    expect(body.tasks[1].status).toBe("todo");
    expect(body.messages[0].unread).toBe(true);
    expect(body.stats).toEqual({
      upcoming_events: 2,
      overdue_tasks: 1,
      unread_messages: 1,
      completed_tasks: 0,
      active_workflows: 0,
      total_agents: 0,
    });
  });

  it("returns backend data and computes stats from it", async () => {
    const past = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const future = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/calendar/events")) {
        return Promise.resolve(
          backendJson({
            events: [
              { id: "e-future", title: "Review", start: future, end: future, status: "confirmed" },
              { id: "e-past", title: "Retro", start: past, end: past, status: "completed" },
            ],
          }),
        );
      }
      if (url.includes("/api/tasks")) {
        return Promise.resolve(
          backendJson({
            tasks: [
              { id: "t-overdue", title: "Ship fix", due_date: past, priority: "high", status: "todo", created_at: past, updated_at: past },
              { id: "t-done", title: "Done task", due_date: future, priority: "low", status: "completed", created_at: past, updated_at: past },
            ],
          }),
        );
      }
      return Promise.resolve(
        backendJson({
          messages: [
            { id: "m-1", platform: "email", subject: "Hi", preview: "…", timestamp: past, unread: true, priority: "high" },
            { id: "m-2", platform: "slack", subject: "", preview: "…", timestamp: past, unread: false, priority: "normal" },
          ],
        }),
      );
    });

    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.calendar).toHaveLength(2);
    expect(body.tasks).toHaveLength(2);
    expect(body.messages).toHaveLength(2);
    expect(body.stats).toEqual({
      upcoming_events: 1,
      overdue_tasks: 1,
      unread_messages: 1,
      completed_tasks: 1,
      active_workflows: 0,
      total_agents: 0,
    });
  });

  it("falls back per-endpoint when a backend endpoint returns an error", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/calendar/events")) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: async () => ({}),
        });
      }
      if (url.includes("/api/tasks")) {
        return Promise.resolve(backendJson({}));
      }
      return Promise.resolve(
        backendJson({
          messages: [
            { id: "m-1", platform: "email", subject: "S", preview: "P", timestamp: new Date().toISOString(), unread: true, priority: "high" },
          ],
        }),
      );
    });
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.calendar[0].id).toBe("mock-1");
    expect(body.tasks).toHaveLength(0);
    expect(body.messages).toHaveLength(1);
    expect(body.stats).toEqual({
      upcoming_events: 2,
      overdue_tasks: 0,
      unread_messages: 1,
      completed_tasks: 0,
      active_workflows: 0,
      total_agents: 0,
    });
  });

  it("queries the configured backend base URL, not the hardcoded dev port", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/calendar/events")) {
        return Promise.resolve(backendJson({ events: [] }));
      }
      if (url.includes("/api/tasks")) {
        return Promise.resolve(backendJson({ tasks: [] }));
      }
      return Promise.resolve(backendJson({ messages: [] }));
    });
    await invoke("GET");
    const calledUrls = mockFetch.mock.calls.map((c: any) => c[0] as string);
    expect(calledUrls.some((u) => u.includes("5058"))).toBe(false);
    expect(calledUrls).toEqual(
      expect.arrayContaining([
        expect.stringContaining("/api/calendar/events"),
        expect.stringContaining("/api/tasks"),
        expect.stringContaining("/api/messages"),
      ]),
    );
  });
});
