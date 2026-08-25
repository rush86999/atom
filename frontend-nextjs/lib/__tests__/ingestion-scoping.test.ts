/**
 * Ingestion scoping API tests (round 80s UI completion).
 *
 * Verifies the typed helpers hit the documented endpoints with the right
 * params: agent listing (governance registry) and scoped enable-sync/sync
 * (role persisted on SyncConfiguration for scheduled auto-syncs).
 */
import { listScopedAgents, enableScopedSync } from "@/lib/ingestion-scoping";
import { apiClient } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

const mockedGet = apiClient.get as jest.Mock;
const mockedPost = apiClient.post as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("listScopedAgents", () => {
  it("returns the raw registry array", async () => {
    const agents = [
      { agent_id: "fin-1", name: "Finance Agent", category: "finance" },
    ];
    mockedGet.mockResolvedValue({ data: agents });
    expect(await listScopedAgents()).toEqual(agents);
    expect(mockedGet).toHaveBeenCalledWith("/api/agent-governance/agents");
  });

  it("unwraps {agents: [...]} envelopes too", async () => {
    const agents = [{ agent_id: "a2", name: "B", category: "sales" }];
    mockedGet.mockResolvedValue({ data: { agents } });
    expect(await listScopedAgents()).toEqual(agents);
  });

  it("returns [] for non-array payloads", async () => {
    mockedGet.mockResolvedValue({ data: null });
    expect(await listScopedAgents()).toEqual([]);
  });
});

describe("enableScopedSync", () => {
  it("posts sync + enable-sync with agent_id param", async () => {
    mockedPost.mockResolvedValue({ data: {} });
    await enableScopedSync("zoho", {
      entityTypes: ["deals"],
      syncLastNDays: 30,
      agentId: "fin-1",
    });
    expect(mockedPost).toHaveBeenCalledWith(
      "/api/data-ingestion/sync/zoho",
      undefined,
      { params: expect.anything() }
    );
    const enableCall = mockedPost.mock.calls.find(
      ([u]: any) => String(u).includes("enable-sync")
    );
    expect(enableCall).toBeDefined();
    expect(enableCall[1]).toMatchObject({
      integration_id: "zoho",
      entity_types: ["deals"],
    });
    const syncParams = enableCall[2].params as URLSearchParams;
    expect(syncParams.get("agent_id")).toBe("fin-1");
  });

  it("omits agent_id when not provided", async () => {
    mockedPost.mockResolvedValue({ data: {} });
    await enableScopedSync("zoho");
    const syncCall = mockedPost.mock.calls.find(
      ([u]: any) => String(u).includes("/sync/")
    );
    expect(syncCall[2]?.params?.agent_id).toBeUndefined();
  });
});
