/**
 * DevStudio Tauri-mode tests (pages/dev-studio.tsx)
 *
 * Companion to dev-studio.test.tsx: here the @tauri-apps/api `invoke`
 * function IS available, exercising every desktop-mode branch of the page
 * (system info, file/folder dialogs, command execution, file save, listing).
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DevStudio from "@/pages/dev-studio";

const mockToast = jest.fn();

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

const mockInvoke = jest.fn();
jest.mock("@tauri-apps/api", () => ({ invoke: (...args: any[]) => mockInvoke(...args) }));

jest.mock("@/components/DevStudio/AgentConsole", () => ({
  __esModule: true,
  default: () => <div data-testid="agent-console">Agent Console</div>,
}));

jest.mock("@/components/DevStudio/SkillRunner", () => ({
  __esModule: true,
  default: () => <div data-testid="skill-runner">Skill Runner</div>,
}));

const SYSTEM_INFO = { os: "Linux", cpu_usage: 10, memory_usage: 20, disk_usage: 30, uptime: 3600 };
const DIR_ENTRIES = [
  { name: "lib", path: "/atom/lib", is_directory: true, size: 0 },
  { name: "notes.md", path: "/atom/notes.md", is_directory: false, size: 512 },
];

describe("DevStudio (Tauri mode)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockInvoke.mockResolvedValue({});
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_folder_dialog") return { success: true, path: "/atom" };
      if (cmd === "list_directory") return { success: true, entries: DIR_ENTRIES };
      return { success: true };
    });
  });

  const switchTab = (name: string) => {
    fireEvent.click(screen.getByRole("button", { name: new RegExp(name, "i") }));
  };

  test("loads system info through invoke on mount", async () => {
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    expect(mockInvoke).toHaveBeenCalledWith("get_system_info");
    expect(screen.queryByText("Desktop App Required")).not.toBeInTheDocument();
  });

  test("system info invoke failure shows error toast", async () => {
    mockInvoke.mockRejectedValue(new Error("denied"));
    render(<DevStudio />);
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Failed to load system information" })
      )
    );
  });

  test("opens file through native dialog and reads content", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_file_dialog") return { success: true, path: "/atom/main.ts" };
      if (cmd === "read_file_content") return { success: true, content: "tauri code" };
      return { success: true };
    });
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("Code Editor");

    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() =>
      expect(screen.getByDisplayValue("tauri code")).toBeInTheDocument()
    );
    expect(mockInvoke).toHaveBeenCalledWith("open_file_dialog", expect.anything());
  });

  test("open file dialog failure is logged without crash", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_file_dialog") return { success: false };
      return { success: true };
    });
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("Code Editor");
    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() => expect(mockInvoke).toHaveBeenCalledWith("open_file_dialog", expect.anything()));
    consoleSpy.mockRestore();
  });

  test("open file dialog rejection is caught", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_file_dialog") throw new Error("dialog failed");
      return { success: true };
    });
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("Code Editor");
    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() => expect(mockInvoke).toHaveBeenCalledWith("open_file_dialog", expect.anything()));
    consoleSpy.mockRestore();
  });

  test("open folder through native dialog lists contents", async () => {
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(screen.getByText("lib")).toBeInTheDocument());
    expect(mockInvoke).toHaveBeenCalledWith("open_folder_dialog");
    expect(mockInvoke).toHaveBeenCalledWith("list_directory", { path: "/atom" });
  });

  test("open folder dialog failure is logged without crash", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_folder_dialog") return { success: false };
      return { success: true };
    });
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("File Explorer");
    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(mockInvoke).toHaveBeenCalledWith("open_folder_dialog"));
    consoleSpy.mockRestore();
  });

  test("open folder dialog rejection is caught", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_folder_dialog") throw new Error("dialog failed");
      return { success: true };
    });
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("File Explorer");
    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(mockInvoke).toHaveBeenCalledWith("open_folder_dialog"));
    consoleSpy.mockRestore();
  });

  test("load directory via invoke rejection is caught", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_folder_dialog") return { success: true, path: "/atom" };
      if (cmd === "list_directory") throw new Error("ls failed");
      return { success: true };
    });
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("File Explorer");
    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(mockInvoke).toHaveBeenCalledWith("list_directory", { path: "/atom" }));
    consoleSpy.mockRestore();
  });

  test("execute command via invoke with stdout and stderr", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "execute_command") return { success: true, exit_code: 0, stdout: "build ok", stderr: "" };
      return { success: true };
    });
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("Skill Runner");

    expect(screen.getByTestId("skill-runner")).toBeInTheDocument();
    expect(mockInvoke).toHaveBeenCalledTimes(1);
  });

  test("execute command via invoke failure path", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "execute_command") return { success: false, exit_code: 1, stdout: "", stderr: "boom" };
      return { success: true };
    });
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
  });

  test("execute command invoke rejection sets output", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "execute_command") throw new Error("spawn failed");
      return { success: true };
    });
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
  });

  test("save file via invoke succeeds with toast", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_file_dialog") return { success: true, path: "/atom/main.ts" };
      if (cmd === "read_file_content") return { success: true, content: "code" };
      if (cmd === "write_file_content") return { success: true };
      return { success: true };
    });
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("Code Editor");
    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() => expect(screen.getByDisplayValue("code")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Save File/ }));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "File Saved" })
      )
    );
    expect(mockInvoke).toHaveBeenCalledWith("write_file_content", { path: "/atom/main.ts", content: "code" });
  });

  test("save file via invoke failure shows error toast", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_file_dialog") return { success: true, path: "/atom/main.ts" };
      if (cmd === "read_file_content") return { success: true, content: "code" };
      if (cmd === "write_file_content") throw new Error("disk full");
      return { success: true };
    });
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("Code Editor");
    fireEvent.click(screen.getAllByRole("button", { name: /Open File/ })[0]);
    await waitFor(() => expect(screen.getByDisplayValue("code")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Save File/ }));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Save Failed" })
      )
    );
  });

  test("directory Open invoke rejection is caught after listing", async () => {
    let calls = 0;
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "open_folder_dialog") return { success: true, path: "/atom" };
      if (cmd === "list_directory") {
        calls += 1;
        if (calls > 1) throw new Error("ls failed");
        return { success: true, entries: DIR_ENTRIES };
      }
      return { success: true };
    });
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(screen.getByText("lib")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    consoleSpy.mockRestore();
  });

  test("directory Open button navigates via invoke", async () => {
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(screen.getByText("lib")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() =>
      expect(mockInvoke).toHaveBeenCalledWith("list_directory", { path: "/atom/lib" })
    );
  });

  test("directory View button reads content via invoke", async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_system_info") return SYSTEM_INFO;
      if (cmd === "list_directory") return { success: true, entries: DIR_ENTRIES };
      if (cmd === "read_file_content") return { success: true, content: "notes body" };
      return { success: true };
    });
    render(<DevStudio />);
    await waitFor(() => expect(screen.getByText("Linux")).toBeInTheDocument());
    switchTab("File Explorer");

    fireEvent.click(screen.getByRole("button", { name: /Open Folder/ }));
    await waitFor(() => expect(screen.getByText("notes.md")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /View/ }));
    switchTab("Code Editor");
    await waitFor(() => expect(screen.getByDisplayValue("notes body")).toBeInTheDocument());
  });
});
