import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DevStudio from "@/pages/dev-studio";
import { useToast } from "@/components/ui/use-toast";

// Tauri mode: invoke is a real (mocked) function, so the desktop branches run.
const mockInvoke = jest.fn();
jest.mock("@tauri-apps/api", () => ({
  invoke: (...args: any[]) => mockInvoke(...args),
}));

jest.mock("@/components/DevStudio/AgentConsole", () => ({
  __esModule: true,
  default: () => <div data-testid="agent-console" />,
}));

jest.mock("@/components/DevStudio/SkillRunner", () => ({
  __esModule: true,
  default: () => <div data-testid="skill-runner" />,
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

describe("DevStudio (tauri mode)", () => {
  const mockToast = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    mockInvoke.mockImplementation((command: string) => {
      if (command === "get_system_info") {
        return Promise.resolve({ os: "Windows", cpu_usage: 10, memory_usage: 20, disk_usage: 30 });
      }
      if (command === "open_file_dialog") {
        return Promise.resolve({ success: true, path: "C:/code/main.ts" });
      }
      if (command === "read_file_content") {
        return Promise.resolve({ success: true, content: "console.log(1)" });
      }
      if (command === "open_folder_dialog") {
        return Promise.resolve({ success: true, path: "C:/code" });
      }
      if (command === "list_directory") {
        return Promise.resolve({
          success: true,
          entries: [{ name: "src", is_directory: true, path: "C:/code/src", size: 0 }],
        });
      }
      if (command === "write_file_content") {
        return Promise.resolve({ success: true });
      }
      return Promise.resolve({ success: true });
    });
  });

  it("loads system info via Tauri invoke without fetching the bridge", async () => {
    render(<DevStudio />);

    await waitFor(() => {
      expect(screen.getByText("Windows")).toBeInTheDocument();
    });
    expect(mockInvoke).toHaveBeenCalledWith("get_system_info");
    // No desktop-app alert in tauri mode
    expect(screen.queryByText("Desktop App Required")).not.toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
  });

  it("shows a toast when Tauri system info fails", async () => {
    mockInvoke.mockRejectedValue(new Error("invoke failed"));

    render(<DevStudio />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error" })
      );
    });
  });

  it("opens a file through the Tauri dialog without prompting", async () => {
    window.prompt = jest.fn() as any;
    render(<DevStudio />);

    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));
    fireEvent.click(screen.getAllByRole("button", { name: /open file/i })[0]);

    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalledWith(
        "open_file_dialog",
        expect.objectContaining({ filters: expect.any(Array) })
      );
    });
    expect(window.prompt).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByText("Editing: C:/code/main.ts")).toBeInTheDocument();
    });
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
      "console.log(1)"
    );
  });

  it("opens a folder through the Tauri dialog and lists its contents", async () => {
    render(<DevStudio />);
    fireEvent.click(screen.getByRole("button", { name: /file explorer/i }));
    fireEvent.click(screen.getByRole("button", { name: /open folder/i }));

    await waitFor(() => {
      expect(screen.getByText("C:/code")).toBeInTheDocument();
    });
    expect(mockInvoke).toHaveBeenCalledWith("open_folder_dialog");
    expect(screen.getByText("src")).toBeInTheDocument();
  });

  it("saves the file through Tauri invoke", async () => {
    window.prompt = jest.fn() as any;
    render(<DevStudio />);
    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));
    fireEvent.click(screen.getAllByRole("button", { name: /open file/i })[0]);
    await waitFor(() => {
      expect(screen.getByText("Editing: C:/code/main.ts")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /save file/i }));

    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalledWith(
        "write_file_content",
        expect.objectContaining({ path: "C:/code/main.ts", content: "console.log(1)" })
      );
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "File Saved" })
    );
  });

  it("shows a save-failed toast when Tauri write rejects", async () => {
    mockInvoke.mockImplementation((command: string) => {
      if (command === "open_file_dialog") {
        return Promise.resolve({ success: true, path: "C:/code/main.ts" });
      }
      if (command === "read_file_content") {
        return Promise.resolve({ success: true, content: "x" });
      }
      if (command === "write_file_content") {
        return Promise.reject(new Error("permission"));
      }
      return Promise.resolve({ success: true });
    });

    window.prompt = jest.fn() as any;
    render(<DevStudio />);
    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));
    fireEvent.click(screen.getAllByRole("button", { name: /open file/i })[0]);
    await waitFor(() => {
      expect(screen.getByText("Editing: C:/code/main.ts")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /save file/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Save Failed" })
      );
    });
  });
});
