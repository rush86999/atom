const mockExistsSync = jest.fn();
const mockMkdirSync = jest.fn();
const mockReadFileSync = jest.fn();
const mockWriteFileSync = jest.fn();
jest.mock("fs", () => ({
  existsSync: mockExistsSync,
  mkdirSync: mockMkdirSync,
  readFileSync: mockReadFileSync,
  writeFileSync: mockWriteFileSync,
}));

import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/v1/tasks/[id]";

const seedTasks = [
  { id: "1", title: "First", status: "todo" },
  { id: "2", title: "Second", status: "in-progress" },
];

describe("pages/api/v1/tasks/[id]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // The "data" directory exists and the tasks file exists by default.
    mockExistsSync.mockImplementation(
      (p: any) => typeof p === "string" && p.includes("data"),
    );
    mockReadFileSync.mockReturnValue(JSON.stringify(seedTasks));
  });

  const invoke = async (method: any, query: any = { id: "1" }, body?: any) => {
    const { req, res } = createMocks({ method, query, body }) as any;
    await handler(req, res);
    return res;
  };

  it("updates a task with PUT and persists the merged result", async () => {
    const res = await invoke("PUT", { id: "1" }, { title: "Updated", status: "done" });
    expect(res._getStatusCode()).toBe(200);
    const { task } = res._getJSONData();
    expect(task).toMatchObject({ id: "1", title: "Updated", status: "done" });
    expect(typeof task.updatedAt).toBe("string");
    expect(mockWriteFileSync).toHaveBeenCalledTimes(1);
    const saved = JSON.parse(mockWriteFileSync.mock.calls[0][1]);
    expect(saved).toHaveLength(2);
    expect(saved[0]).toEqual(task);
    expect(saved[1]).toEqual(seedTasks[1]);
    // Directory already existed, so no mkdir happened.
    expect(mockMkdirSync).not.toHaveBeenCalled();
  });

  it("creates the data directory when it does not exist", async () => {
    // Every existsSync check fails: dir missing AND data file missing.
    mockExistsSync.mockReturnValue(false);
    const res = await invoke("PUT", { id: "1" }, { title: "Updated" });
    expect(res._getStatusCode()).toBe(404);
    expect(mockMkdirSync).toHaveBeenCalledWith(
      expect.stringContaining("data"),
      { recursive: true },
    );
  });

  it("returns 404 on PUT when the task does not exist", async () => {
    const res = await invoke("PUT", { id: "999" }, { title: "Nope" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "Task not found" });
    expect(mockWriteFileSync).not.toHaveBeenCalled();
  });

  it("returns 404 on PUT when the data file does not exist", async () => {
    mockExistsSync.mockImplementation(() => false);
    const res = await invoke("PUT", { id: "1" }, { title: "Updated" });
    expect(res._getStatusCode()).toBe(404);
    expect(mockReadFileSync).not.toHaveBeenCalled();
  });

  it("treats a corrupt data file as empty on PUT", async () => {
    mockReadFileSync.mockReturnValue("not-json{");
    const res = await invoke("PUT", { id: "1" }, { title: "Updated" });
    expect(res._getStatusCode()).toBe(404);
  });

  it("deletes a task with DELETE and persists the remainder", async () => {
    const res = await invoke("DELETE", { id: "2" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true });
    const saved = JSON.parse(mockWriteFileSync.mock.calls[0][1]);
    expect(saved).toHaveLength(1);
    expect(saved[0].id).toBe("1");
  });

  it("returns 404 on DELETE when the task does not exist", async () => {
    const res = await invoke("DELETE", { id: "404" });
    expect(res._getStatusCode()).toBe(404);
    expect(res._getJSONData()).toEqual({ error: "Task not found" });
    expect(mockWriteFileSync).not.toHaveBeenCalled();
  });

  it("rejects unsupported methods with 405", async () => {
    const res = await invoke("GET", { id: "1" });
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });
});
