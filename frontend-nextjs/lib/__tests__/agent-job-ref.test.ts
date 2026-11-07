import {
  rememberAgentJob,
  loadAgentJob,
  loadLastAgentJob,
  forgetAgentJob,
  forgetAgentJobIfCurrent,
} from "../agent-job-ref";

describe("agent job reference cache", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  test("stores only an opaque locator per signed-in user and agent", () => {
    rememberAgentJob("user-a", "agent-1", "job-1");
    expect(loadAgentJob("user-a", "agent-1")).toEqual({
      agentId: "agent-1",
      jobId: "job-1",
    });
    expect(loadLastAgentJob("user-a")).toEqual({
      agentId: "agent-1",
      jobId: "job-1",
    });
  });

  test("a different signed-in user cannot reuse another user's cached ref", () => {
    rememberAgentJob("user-a", "agent-1", "job-1");
    expect(loadAgentJob("user-b", "agent-1")).toBeNull();
    expect(loadLastAgentJob("user-b")).toBeNull();
    expect(loadAgentJob("user-a", "agent-2")).toBeNull();
  });

  test("malformed or partial cached values are ignored, not trusted", () => {
    window.localStorage.setItem("atom.agent-job.last.user-a", "{not-json");
    expect(loadLastAgentJob("user-a")).toBeNull();
    window.localStorage.setItem(
      "atom.agent-job.last.user-a",
      JSON.stringify({ agentId: "agent-1" }),
    );
    expect(loadLastAgentJob("user-a")).toBeNull();
  });

  test("a stale forget cannot erase a newer job for the same agent", () => {
    rememberAgentJob("user-a", "agent-1", "job-old");
    rememberAgentJob("user-a", "agent-1", "job-new");

    forgetAgentJobIfCurrent("user-a", "agent-1", "job-old");
    expect(loadAgentJob("user-a", "agent-1")?.jobId).toBe("job-new");

    forgetAgentJobIfCurrent("user-a", "agent-1", "job-new");
    expect(loadAgentJob("user-a", "agent-1")).toBeNull();
    expect(loadLastAgentJob("user-a")).toBeNull();
  });

  test("forgetting one agent leaves another agent's last ref intact", () => {
    rememberAgentJob("user-a", "agent-1", "job-1");
    rememberAgentJob("user-a", "agent-2", "job-2");
    forgetAgentJob("user-a", "agent-1");

    expect(loadAgentJob("user-a", "agent-1")).toBeNull();
    expect(loadAgentJob("user-a", "agent-2")?.jobId).toBe("job-2");
    expect(loadLastAgentJob("user-a")?.agentId).toBe("agent-2");
  });
});
