import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/projects/data";

describe("pages/api/projects/data", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const invoke = () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    handler(req, res);
    // The handler answers from inside a 1s setTimeout; fire it synchronously.
    jest.advanceTimersByTime(1000);
    return res;
  };

  it("returns the mock project management data after the simulated delay", () => {
    const res = invoke();
    expect(res._getStatusCode()).toBe(200);
    const data = res._getJSONData();

    expect(data.project).toEqual({
      id: "proj-apollo",
      name: "Project Apollo",
      description:
        "A mission to revolutionize space travel through AI-driven logistics.",
      status: "On Track",
    });
    expect(data.tasks).toHaveLength(5);
    expect(data.tasks[0]).toEqual({
      id: "task-101",
      title: "Develop propulsion system prototype",
      status: "In Progress",
      assignee: "Alex Ray",
    });
    expect(data.team).toEqual([
      { id: "team-1", name: "Alex Ray", role: "Lead Engineer" },
      { id: "team-2", name: "Casey Jordan", role: "UX/UI Designer" },
    ]);
    expect(data.activityStream).toHaveLength(3);
    expect(data.activityStream[0].id).toBe("act-1");
  });

  it("does not respond before the simulated delay elapses", () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    handler(req, res);
    jest.advanceTimersByTime(999);
    expect(res._getStatusCode()).toBe(200); // node-mocks-http default
    expect(() => res._getJSONData()).toThrow();
  });
});
