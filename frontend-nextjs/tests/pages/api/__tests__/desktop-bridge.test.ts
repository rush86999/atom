const mockExec = jest.fn();
const mockExecFile = jest.fn();
const mockExistsSync = jest.fn();
const mockReadFileSync = jest.fn();
const mockWriteFileSync = jest.fn();
const mockReaddirSync = jest.fn();
const mockStatSync = jest.fn();

jest.mock("fs", () => {
  const real = jest.requireActual("fs");
  return {
    ...real,
    existsSync: mockExistsSync,
    readFileSync: mockReadFileSync,
    writeFileSync: mockWriteFileSync,
    readdirSync: mockReaddirSync,
    statSync: mockStatSync,
  };
});

jest.mock("child_process", () => {
  const real = jest.requireActual("child_process");
  return { ...real, exec: mockExec, execFile: mockExecFile };
});

import path from "path";
import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/dev/desktop-bridge";

describe("pages/api/dev/desktop-bridge", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
  });

  it("returns system info for get_system_info", async () => {
    const res = await invoke("POST", { command: "get_system_info" });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.os).toEqual(expect.any(String));
    expect(body.cpu_usage).toBeGreaterThan(0);
    expect(body.memory_usage).toBeGreaterThanOrEqual(0);
    expect(body.memory_usage).toBeLessThanOrEqual(100);
    expect(body.disk_usage).toBe(52.4);
    expect(body.uptime).toBeGreaterThan(0);
  });

  it("returns 400 when read_file_content has no path", async () => {
    const res = await invoke("POST", { command: "read_file_content", args: {} });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Path is required");
  });

  it("returns 400 instead of 500 when read_file_content has no args at all", async () => {
    const res = await invoke("POST", { command: "read_file_content" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Path is required");
  });

  it("returns 400 when the file does not exist", async () => {
    mockExistsSync.mockReturnValue(false);
    const res = await invoke("POST", {
      command: "read_file_content",
      args: { path: `${process.cwd()}/nope.txt` },
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("File does not exist");
  });

  it("reads file content when the file exists", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue("hello from file");
    const res = await invoke("POST", {
      command: "read_file_content",
      args: { path: `${process.cwd()}/real.txt` },
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true, content: "hello from file" });
    expect(mockReadFileSync).toHaveBeenCalledWith(path.join(process.cwd(), "real.txt"), "utf8");
  });

  it("returns 400 when write_file_content has no path", async () => {
    const res = await invoke("POST", { command: "write_file_content", args: {} });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Path is required");
  });

  it("returns 400 instead of 500 when write_file_content has no args at all", async () => {
    const res = await invoke("POST", { command: "write_file_content" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Path is required");
  });

  it("writes file content and returns success", async () => {
    const res = await invoke("POST", {
      command: "write_file_content",
      args: { path: `${process.cwd()}/out.txt`, content: "data" },
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ success: true });
    expect(mockWriteFileSync).toHaveBeenCalledWith(path.join(process.cwd(), "out.txt"), "data", "utf8");
  });

  it("writes an empty string when content is omitted", async () => {
    const res = await invoke("POST", {
      command: "write_file_content",
      args: { path: `${process.cwd()}/out.txt` },
    });
    expect(res._getStatusCode()).toBe(200);
    expect(mockWriteFileSync).toHaveBeenCalledWith(path.join(process.cwd(), "out.txt"), "", "utf8");
  });

  it("returns 400 when list_directory target does not exist", async () => {
    mockExistsSync.mockReturnValue(false);
    const res = await invoke("POST", {
      command: "list_directory",
      args: { path: `${process.cwd()}/ghost` },
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().error).toBe("Directory does not exist");
  });

  it("falls back to the working directory when list_directory has no args", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReaddirSync.mockReturnValue(["cwd-file.txt"]);
    mockStatSync.mockReturnValue({ isDirectory: () => false, size: 42 });
    const res = await invoke("POST", { command: "list_directory" });
    expect(res._getStatusCode()).toBe(200);
    const { entries } = res._getJSONData();
    expect(entries).toEqual([
      {
        name: "cwd-file.txt",
        path: `${process.cwd()}/cwd-file.txt`,
        is_directory: false,
        size: 42,
      },
    ]);
    expect(mockExistsSync).toHaveBeenCalledWith(process.cwd());
  });

  it("lists directory entries, tolerating per-entry stat failures", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReaddirSync.mockReturnValue(["a.txt", "b"]);
    mockStatSync.mockImplementation((p: string) => {
      if (p.endsWith("b")) throw new Error("stat failed");
      return { isDirectory: () => false, size: 123 };
    });
    const res = await invoke("POST", {
      command: "list_directory",
      args: { path: `${process.cwd()}/dir` },
    });
    expect(res._getStatusCode()).toBe(200);
    const { entries } = res._getJSONData();
    expect(entries).toHaveLength(2);
    expect(entries[0]).toEqual({
      name: "a.txt",
      path: path.join(process.cwd(), "dir", "a.txt"),
      is_directory: false,
      size: 123,
    });
    expect(entries[1]).toEqual({
      name: "b",
      path: path.join(process.cwd(), "dir", "b"),
      is_directory: false,
      size: 0,
    });
  });

  it("executes an allowlisted command and returns its stdout on success", async () => {
    mockExecFile.mockImplementation((_bin: string, _args: any, _opts: any, cb: any) => {
      cb(null, "hello out", "");
    });
    const res = await invoke("POST", {
      command: "execute_command",
      args: { command: "node --version" },
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      output: "hello out",
      exit_code: 0,
      stdout: "hello out",
      stderr: "",
    });
    expect(mockExecFile).toHaveBeenCalledWith(
      "node",
      ["--version"],
      expect.objectContaining({ cwd: expect.any(String) }),
      expect.any(Function),
    );
  });

  it("reports exit code and stderr when a command fails", async () => {
    const err: any = new Error("boom");
    err.code = 2;
    mockExecFile.mockImplementation((_bin: string, _args: any, _opts: any, cb: any) => {
      cb(err, "", "some stderr");
    });
    const res = await invoke("POST", {
      command: "execute_command",
      args: { command: "node --version" },
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: false,
      output: "\nError: some stderr",
      exit_code: 2,
      stdout: "",
      stderr: "some stderr",
    });
  });

  it("runs allowlisted commands against the resolved working directory", async () => {
    mockExecFile.mockImplementation((_bin: string, _args: any, _opts: any, cb: any) => {
      cb(null, "", "");
    });
    await invoke("POST", { command: "execute_command", args: { command: "npm --version" } });
    expect(mockExecFile).toHaveBeenCalledWith(
      "npm",
      ["--version"],
      expect.objectContaining({ cwd: path.resolve(process.cwd()) }),
      expect.any(Function),
    );
  });

  it("rejects non-allowlisted commands with 403", async () => {
    const res = await invoke("POST", {
      command: "execute_command",
      args: { command: "echo hi" },
    });
    expect(res._getStatusCode()).toBe(403);
    expect(res._getJSONData()).toEqual({
      success: false,
      error: "Command not in allowlist. Only safe read-only commands are permitted.",
    });
  });

  it("rejects unknown bridge commands with 400", async () => {
    const res = await invoke("POST", { command: "rm_rf", args: {} });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({ error: "Command rm_rf not supported" });
  });
});
