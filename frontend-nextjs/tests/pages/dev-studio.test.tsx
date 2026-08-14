/**
 * DevStudio page tests (pages/dev-studio.tsx, was 0% coverage)
 *
 * The page runs in "web mode" in jsdom (Tauri invoke unavailable), so every
 * action routes through POST /api/dev/desktop-bridge. Covers system info
 * load/refresh, file/folder open (prompt-based), directory browsing,
 * command execution, file read/save, and the editor workflow.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DevStudio from "@/pages/dev-studio";

const mockToast = jest.fn();

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

jest.mock("@tauri-apps/api", () => ({ invoke: null }));

jest.mock("@/components/DevStudio/AgentConsole", () => ({
  __esModule: true,
  default: () => <div data-testid="agent-console">Agent Console</div>,
}));

jest.mock("@/components/DevStudio/SkillRunner", () => ({
  __esModule: true,
  default: () => <div data-testid="skill-runner">Skill Runner</div>,
}));

const okJson = (body: any) => ({ ok: true, json: async () => body });

const bridgeOk = (body: any) => okJson({ success: true, ...body });

const SYSTEM_INFO = {
  os: "macOS",
  cpu_usage: 42,
  memory_usage: 61,
  disk_usage: 33,
  uptime: 7325,
};

const DIR_ENTRIES = [
  { name: "src", path: "/proj/src", is_directory: true, size: 0 },
  { name: "README.md", path: "/proj/README.md", is_directory: false, size: 2048 },
];

describe("DevStudio", () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
    global.prompt = jest.fn();
  });

  const mockBridge = (handler: (body: any) => any) => {
    mockFetch.mockImplementation(async (_url: string, init?: any) => {
      const body = JSON.parse((init as any)?.body || "{}");
      return bridgeOk(handler(body));
    });
  };

  const switchTab = (name: string) => {
    fireEvent.click(screen.getByRole("button", { name: new RegExp(name, "i") }));
  };

  test("shows desktop app alert and loads system info on mount (web mode)", async () => {
    mockBridge(() => SYSTEM_INFO);
    render(<DevStudio />);

    expect(screen.getByText("Dev Studio")).toBeInTheDocument();
    expect(screen.getByText("Desktop App Required")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/dev/desktop-bridge",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("get_system_info"),
      })
    );
  });

  test("renders platform badges with system info values", async () => {
    mockBridge(() => SYSTEM_INFO);
    render(<DevStudio />);

    await waitFor(() => expect(screen.getByText("42%")).toBeInTheDocument());
    expect(screen.getByText("61%")).toBeInTheDocument();
    expect(screen.getByText("33%")).toBeInTheDocument();
    expect(screen.getByText("2h 2m")).toBeInTheDocument();
  });

  test("refresh system info button reloads info", async () => {
    mockBridge(() => SYSTEM_INFO);
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Refresh System Info/ }));
    expect(mockFetch.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  test("system info fetch failure is logged without crashing", async () => {
    mockFetch.mockRejectedValue(new Error("bridge down"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    expect(screen.getByText("Loading system information...")).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  test("opens folder via prompt and lists directory contents", async () => {
    mockBridge((body: any) => {
      if (body.command === "list_directory") return { entries: DIR_ENTRIES };
      return SYSTEM_INFO;
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj");
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(screen.getByText("src")).toBeInTheDocument());
    expect(screen.getByText("/proj")).toBeInTheDocument();
    expect(screen.getByText("Directory")).toBeInTheDocument();
    expect(screen.getByText("File")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  test("folder list failure surfaces error toast", async () => {
    mockBridge((body: any) => {
      if (body.command === "list_directory") return { success: false, error: "Permission denied" };
      return SYSTEM_INFO;
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj");
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Permission denied" })
      )
    );
  });

  test("open folder prompt cancellation leaves directory empty", async () => {
    mockBridge(() => SYSTEM_INFO);
    (global.prompt as jest.Mock).mockReturnValue(null);
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    expect(screen.getByText("No folder selected")).toBeInTheDocument();
  });

  test("opens file via prompt and loads its content into editor", async () => {
    mockBridge((body: any) => {
      if (body.command === "read_file_content") return { content: "console.log('hi');" };
      return SYSTEM_INFO;
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj/main.ts");
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("Code Editor");

    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() =>
      expect(screen.getByDisplayValue("console.log('hi');")).toBeInTheDocument()
    );
  });

  test("file read failure shows error toast", async () => {
    mockBridge((body: any) => {
      if (body.command === "read_file_content") return { success: false, error: "Not found" };
      return SYSTEM_INFO;
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj/main.ts");
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("Code Editor");

    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Not found" })
      )
    );
  });

  test("saves edited file content via bridge", async () => {
    mockBridge((body: any) => {
      if (body.command === "read_file_content") return { content: "old" };
      return { success: true };
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj/main.ts");
    render(<DevStudio />);
    switchTab("Code Editor");
    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() =>
      expect(screen.getByDisplayValue("old")).toBeInTheDocument()
    );

    const editor = screen.getByDisplayValue("old");
    fireEvent.change(editor, { target: { value: "new content" } });

    fireEvent.click(screen.getByRole("button", { name: /Save File/ }));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "File Saved", description: "Successfully saved /proj/main.ts" })
      )
    );
  });

  test("save failure shows error toast", async () => {
    mockBridge((body: any) => {
      if (body.command === "read_file_content") return { content: "old" };
      return { success: false, error: "Disk full" };
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj/main.ts");
    render(<DevStudio />);
    switchTab("Code Editor");
    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() =>
      expect(screen.getByDisplayValue("old")).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /Save File/ }));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Save Failed", description: "Disk full" })
      )
    );
  });

  test("save fetch rejection shows error toast", async () => {
    mockBridge((body: any) => {
      if (body.command === "read_file_content") return { content: "old" };
      throw new Error("offline");
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj/main.ts");
    render(<DevStudio />);
    switchTab("Code Editor");
    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() =>
      expect(screen.getByDisplayValue("old")).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /Save File/ }));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Save Failed", description: expect.stringContaining("offline") })
      )
    );
  });

  test("executes command and renders output when success", async () => {
    mockBridge((body: any) => {
      if (body.command === "execute_command") {
        return { exit_code: 0, stdout: "hello world", stderr: "" };
      }
      return SYSTEM_INFO;
    });
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Skill Runner/ }));
    expect(screen.getByTestId("skill-runner")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /File Explorer/ }));
    expect(screen.getByRole("button", { name: /Open Folder/ })).toBeInTheDocument();
  });

  test("agent tab renders AgentConsole", async () => {
    mockBridge(() => SYSTEM_INFO);
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Agent/ }));
    expect(screen.getByTestId("agent-console")).toBeInTheDocument();
  });

  test("editor tab shows no-file-selected state without a file", async () => {
    mockBridge(() => SYSTEM_INFO);
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("Code Editor");
    expect(screen.getAllByText("No file selected").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Save File/ })).not.toBeInTheDocument();
  });

  test("directory Open fetch rejection is caught", async () => {
    mockFetch.mockImplementation(async (_url: string, init?: any) => {
      const body = JSON.parse((init as any)?.body || "{}");
      if (body.command === "list_directory") throw new Error("bridge down");
      return bridgeOk(SYSTEM_INFO);
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj");
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    consoleSpy.mockRestore();
  });

  test("open folder fetch rejection is caught", async () => {
    mockFetch.mockImplementation(async () => {
      throw new Error("bridge down");
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj");
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    switchTab("File Explorer");
    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(consoleSpy).toHaveBeenCalledTimes(2));
    consoleSpy.mockRestore();
  });

  test("read file fetch rejection is caught", async () => {
    mockFetch.mockImplementation(async (_url: string, init?: any) => {
      const body = JSON.parse((init as any)?.body || "{}");
      if (body.command === "read_file_content") throw new Error("read failed");
      return bridgeOk(SYSTEM_INFO);
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj/main.ts");
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("Code Editor");
    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    consoleSpy.mockRestore();
  });

  test("directory Open fetch rejection is caught after listing", async () => {
    let calls = 0;
    mockFetch.mockImplementation(async (_url: string, init?: any) => {
      const body = JSON.parse((init as any)?.body || "{}");
      if (body.command === "list_directory") {
        calls += 1;
        if (calls > 1) throw new Error("bridge down");
        return bridgeOk({ entries: DIR_ENTRIES });
      }
      return bridgeOk(SYSTEM_INFO);
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj");
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(screen.getByText("src")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    consoleSpy.mockRestore();
  });

  test("directory Open button navigates into subdirectory", async () => {
    mockBridge((body: any) => {
      if (body.command === "list_directory") {
        if (body.args?.path === "/proj/src") return { entries: [{ name: "app.ts", path: "/proj/src/app.ts", is_directory: false, size: 1024 }] };
        return { entries: DIR_ENTRIES };
      }
      return SYSTEM_INFO;
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj");
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(screen.getByText("src")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() => expect(screen.getByText("app.ts")).toBeInTheDocument());
    expect(screen.getByText("/proj/src")).toBeInTheDocument();
  });

  test("directory View button reads the file content", async () => {
    mockBridge((body: any) => {
      if (body.command === "read_file_content") return { content: "file body" };
      if (body.command === "list_directory") return { entries: DIR_ENTRIES };
      return SYSTEM_INFO;
    });
    (global.prompt as jest.Mock).mockReturnValue("/proj");
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("macOS")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(screen.getByText("README.md")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /View/ }));
    switchTab("Code Editor");
    await waitFor(() => expect(screen.getByDisplayValue("file body")).toBeInTheDocument());
  });
});
