import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/crm/data";

describe("pages/api/crm/data", () => {
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

  it("returns the mock CRM data after the simulated delay", () => {
    const res = invoke();
    expect(res._getStatusCode()).toBe(200);
    const data = res._getJSONData();

    expect(data.opportunities).toHaveLength(3);
    expect(data.opportunities[0]).toEqual({
      id: "opp1",
      name: "Synergy Corp Website Revamp",
      stage: "Qualification",
      value: 120000,
    });
    expect(data.contacts).toHaveLength(3);
    expect(data.contacts[2]).toEqual({
      id: "cont3",
      name: "Samantha Williams",
      opportunityId: "opp3",
    });
    expect(data.tasks).toHaveLength(3);
    expect(data.tasks[0]).toEqual({
      id: "task1",
      description: "Schedule discovery call with Synergy Corp",
      dueDate: "2024-08-05",
    });
  });

  it("does not respond before the simulated delay elapses", () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    handler(req, res);
    jest.advanceTimersByTime(999);
    expect(res._getStatusCode()).toBe(200); // node-mocks-http default
    expect(() => res._getJSONData()).toThrow();
  });
});
