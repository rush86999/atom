import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import DevStudio from "@/pages/dev-studio";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@tauri-apps/api", (): any => ({ invoke: null }));

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

const SYSTEM_INFO = {
  os: "macOS",
  cpu_usage: 34,
  memory_usage: 61,
  disk_usage: 72,
  uptime: 3661,
  platform: "darwin",
};

const DIRECTORY = {
  success: true,
  entries: [
    { name: "src", is_directory: true, path: "/repo/src", size: 0 },
    { name: "README.md", is_directory: false, path: "/repo/README.md", size: 2048 },
  ],
};

describe("DevStudio (web mode)", () => {
  const mockToast = jest.fn();
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      const body = JSON.parse(String((options as any)?.body) || "{}");
      if (body.command === "get_system_info") {
        return Promise.resolve({ ok: true, json: async () => SYSTEM_INFO });
      }
      if (body.command === "list_directory") {
        return Promise.resolve({ ok: true, json: async () => DIRECTORY });
      }
      if (body.command === "read_file_content") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, content: "# README\nHello" }),
        });
      }
      if (body.command === "write_file_content") {
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ success: false }) });
    });
  });

  it("renders the header, desktop-app alert and all tabs", () => {
    render(<DevStudio />);

    expect(screen.getByRole("heading", { name: /dev studio/i })).toBeInTheDocument();
    expect(screen.getByText("Desktop App Required")).toBeInTheDocument();
    expect(
      screen.getByText(/only available in the ATOM desktop application/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /file explorer/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /skill runner/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /code editor/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /agent/i })).toBeInTheDocument();
  });

  it("loads and displays system information through the desktop bridge", async () => {
    render(<DevStudio />);

    // Loading placeholders before the bridge responds
    expect(screen.getByText("Loading system information...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("macOS")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/dev/desktop-bridge",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ command: "get_system_info" }),
      })
    );
    expect(screen.getByText("34%")).toBeInTheDocument();
    expect(screen.getByText("61%")).toBeInTheDocument();
    expect(screen.getByText("72%")).toBeInTheDocument();
    // uptime 3661s → 1h 1m
    expect(screen.getByText("1h 1m")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("refreshes system info when the refresh button is clicked", async () => {
    render(<DevStudio />);
    await waitFor(() => {
      expect(screen.getByText("macOS")).toBeInTheDocument();
    });
    const callsAfterMount = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: /refresh system info/i }));

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterMount);
    });
  });

  it("opens a file via prompt and shows its content in the editor", async () => {
    window.prompt = jest.fn(() => "/repo/README.md") as any;
    render(<DevStudio />);

    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));

    await waitFor(() => {
      expect(screen.getAllByText("No file selected").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole("button", { name: /open file/i })[0]);

    await waitFor(() => {
      expect(screen.getByText("Editing: /repo/README.md")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
        "# README\nHello"
      );
    });
  });

  it("shows an error toast when reading a file via the bridge fails", async () => {
    window.prompt = jest.fn(() => "/repo/secret.txt") as any;
    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      const body = JSON.parse(String((options as any)?.body) || "{}");
      if (body.command === "read_file_content") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: false, error: "Permission denied" }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ success: true, content: "" }),
      });
    });

    render(<DevStudio />);
    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));
    fireEvent.click(screen.getAllByRole("button", { name: /open file/i })[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Permission denied" })
      );
    });
  });

  it("opens a folder via prompt and lists its contents", async () => {
    window.prompt = jest.fn(() => "/repo") as any;
    render(<DevStudio />);

    fireEvent.click(screen.getByRole("button", { name: /file explorer/i }));
    fireEvent.click(screen.getByRole("button", { name: /open folder/i }));

    await waitFor(() => {
      expect(screen.getByText("/repo")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("src")).toBeInTheDocument();
    });
    expect(screen.getByText("Directory")).toBeInTheDocument();
    expect(screen.getByText("README.md")).toBeInTheDocument();
    expect(screen.getByText("File")).toBeInTheDocument();
    // 2048 bytes → 2.0 KB
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  it("navigates into a directory from the explorer", async () => {
    window.prompt = jest.fn(() => "/repo") as any;
    render(<DevStudio />);
    fireEvent.click(screen.getByRole("button", { name: /file explorer/i }));
    fireEvent.click(screen.getByRole("button", { name: /open folder/i }));

    await waitFor(() => {
      expect(screen.getByText("src")).toBeInTheDocument();
    });

    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      const body = JSON.parse(String((options as any)?.body) || "{}");
      if (body.command === "list_directory") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            success: true,
            entries: [{ name: "index.ts", is_directory: false, path: "/repo/src/index.ts", size: 512 }],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ success: false }) });
    });

    fireEvent.click(screen.getByRole("button", { name: /^open$/i }));

    await waitFor(() => {
      expect(screen.getByText("index.ts")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("/repo/src")).toBeInTheDocument();
    });
  });

  it("views a file from the explorer through the bridge (web mode)", async () => {
    window.prompt = jest.fn(() => "/repo") as any;
    render(<DevStudio />);
    fireEvent.click(screen.getByRole("button", { name: /file explorer/i }));
    fireEvent.click(screen.getByRole("button", { name: /open folder/i }));

    await waitFor(() => {
      expect(screen.getByText("README.md")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /view/i }));

    // No crash in web mode (BUG: previously called the missing Tauri invoke)
    await waitFor(() => {
      expect(screen.getByText("src")).toBeInTheDocument();
    });
    // Content is now loaded into the editor
    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));
    await waitFor(() => {
      expect(screen.getByText("Editing: /repo/README.md")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
        "# README\nHello"
      );
    });
  });

  it("saves the edited file content via the bridge", async () => {
    window.prompt = jest.fn(() => "/repo/README.md") as any;
    render(<DevStudio />);

    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));
    fireEvent.click(screen.getAllByRole("button", { name: /open file/i })[0]);
    await waitFor(() => {
      expect(screen.getByText("Editing: /repo/README.md")).toBeInTheDocument();
    });

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "# README\nEdited" } });
    fireEvent.click(screen.getByRole("button", { name: /save file/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/dev/desktop-bridge",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            command: "write_file_content",
            args: { path: "/repo/README.md", content: "# README\nEdited" },
          }),
        })
      );
    });
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "File Saved" })
      );
    });
  });

  it("shows a save-failed toast when the bridge reports failure", async () => {
    window.prompt = jest.fn(() => "/repo/README.md") as any;
    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      const body = JSON.parse(String((options as any)?.body) || "{}");
      if (body.command === "write_file_content") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: false, error: "Disk full" }),
        });
      }
      if (body.command === "read_file_content") {
        return Promise.resolve({ ok: true, json: async () => ({ success: true, content: "x" }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ success: false }) });
    });

    render(<DevStudio />);
    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));
    fireEvent.click(screen.getAllByRole("button", { name: /open file/i })[0]);
    await waitFor(() => {
      expect(screen.getByText("Editing: /repo/README.md")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /save file/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Save Failed", description: "Disk full" })
      );
    });
  });

  it("renders the Skill Runner and Agent panels", async () => {
    render(<DevStudio />);

    fireEvent.click(screen.getByRole("button", { name: /skill runner/i }));
    expect(screen.getByTestId("skill-runner")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /agent/i }));
    expect(screen.getByTestId("agent-console")).toBeInTheDocument();
  });

  it("does not open a file when the prompt is cancelled", async () => {
    window.prompt = jest.fn((): null => null) as any;
    render(<DevStudio />);
    fireEvent.click(screen.getByRole("button", { name: /code editor/i }));
    fireEvent.click(screen.getAllByRole("button", { name: /open file/i })[0]);

    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getAllByText("No file selected").length).toBeGreaterThan(0);
    expect(
      mockFetch.mock.calls.filter((c: any[]) =>
        String((c[1] as any)?.body).includes("read_file_content")
      )
    ).toHaveLength(0);
  });
});
