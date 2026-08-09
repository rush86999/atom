import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LocalModelsPage from "@/pages/settings/local-models";
import { apiClient } from "@/lib/api-client";

jest.mock("@/lib/api-client", () => ({
  apiClient: { get: jest.fn(), post: jest.fn(), delete: jest.fn() },
}));

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockGet = apiClient.get as jest.Mock;
const mockPost = apiClient.post as jest.Mock;
const mockDelete = apiClient.delete as jest.Mock;

const PROVIDERS = [
  {
    id: "p1",
    name: "My Ollama",
    provider_type: "ollama",
    base_url: "http://localhost:11434/v1",
    is_active: true,
    has_api_key: false,
  },
  {
    id: "p2",
    name: "vLLM Server",
    provider_type: "vllm",
    base_url: "http://localhost:8000/v1",
    is_active: false,
    has_api_key: true,
  },
];

describe("LocalModelsPage", () => {
  let alertSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    alertSpy = jest.spyOn(window, "alert").mockImplementation(() => {});
    mockGet.mockResolvedValue({ data: PROVIDERS });
  });

  it("shows the loading skeleton before providers arrive", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    const { container } = render(<LocalModelsPage />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(2);
  });

  it("shows the empty state when no providers are registered", async () => {
    mockGet.mockResolvedValue({ data: [] });

    render(<LocalModelsPage />);

    await waitFor(() => {
      expect(screen.getByText(/no local providers registered yet/i)).toBeInTheDocument();
    });
  });

  it("renders registered providers with type and base URL", async () => {
    render(<LocalModelsPage />);

    await waitFor(() => {
      expect(screen.getByText("My Ollama")).toBeInTheDocument();
    });
    expect(mockGet).toHaveBeenCalledWith("/api/local-models");
    expect(screen.getByText("ollama • http://localhost:11434/v1")).toBeInTheDocument();
    expect(screen.getByText("vLLM Server")).toBeInTheDocument();
    expect(screen.getByText("vllm • http://localhost:8000/v1")).toBeInTheDocument();
  });

  it("adds a provider: posts the form, closes it and refetches the list", async () => {
    mockPost.mockResolvedValue({ data: { success: true } });

    render(<LocalModelsPage />);
    await waitFor(() => expect(screen.getByText("My Ollama")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /add provider/i }));

    fireEvent.change(screen.getByPlaceholderText(/name/i), {
      target: { value: "LocalAI Box" },
    });
    fireEvent.change(screen.getByPlaceholderText(/base url/i), {
      target: { value: "http://localhost:8080/v1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^register$/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/local-models", {
        name: "LocalAI Box",
        provider_type: "ollama",
        base_url: "http://localhost:8080/v1",
        api_key: undefined,
      });
    });
    // Form closes after registration
    expect(screen.queryByRole("button", { name: /^register$/i })).not.toBeInTheDocument();
    // List refetched
    expect(mockGet.mock.calls.filter(([url]) => url === "/api/local-models").length).toBeGreaterThanOrEqual(2);
  });

  it("keeps the Register button disabled until a name is provided", async () => {
    render(<LocalModelsPage />);
    await waitFor(() => expect(screen.getByText("My Ollama")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /add provider/i }));
    // Base URL is pre-filled in the form state; name is the real gate
    expect(screen.getByRole("button", { name: /^register$/i })).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/name/i), { target: { value: "Box" } });
    expect(screen.getByRole("button", { name: /^register$/i })).toBeEnabled();
  });

  it("deletes a provider and refetches the list", async () => {
    mockDelete.mockResolvedValue({ data: { success: true } });

    render(<LocalModelsPage />);
    await waitFor(() => expect(screen.getByText("My Ollama")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /delete/i })[0]);

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith("/api/local-models/p1");
    });
  });

  it("discovers models and renders capability badges", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/models")) {
        return Promise.resolve({ data: { models: ["llama3:8b", "qwen2.5:7b"] } });
      }
      if (url.includes("/capabilities")) {
        return Promise.resolve({
          data: [
            { model_id: "llama3:8b", supports_tools: true, supports_vision: true, supports_reasoning: false, quality_score: 0.8, speed_score: 0.6, context_window: 8192 },
            { model_id: "qwen2.5:7b", supports_tools: false, supports_vision: false, supports_reasoning: true, quality_score: 0.55, speed_score: 0.9, context_window: 32768 },
          ],
        });
      }
      return Promise.resolve({ data: PROVIDERS });
    });

    render(<LocalModelsPage />);
    await waitFor(() => expect(screen.getByText("My Ollama")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /discover/i })[0]);

    await waitFor(() => {
      expect(screen.getByText("Discovered Models (2):")).toBeInTheDocument();
    });
    expect(mockGet).toHaveBeenCalledWith("/api/local-models/p1/models");
    expect(mockGet).toHaveBeenCalledWith("/api/local-models/p1/capabilities");
    expect(screen.getByText("llama3:8b")).toBeInTheDocument();
    expect(screen.getByText("qwen2.5:7b")).toBeInTheDocument();
    expect(screen.getByText("tools")).toBeInTheDocument();
    expect(screen.getByText("vision")).toBeInTheDocument();
    expect(screen.getByText("reasoning")).toBeInTheDocument();
    expect(screen.getByText("Q: 80%")).toBeInTheDocument();
    expect(screen.getByText("Q: 55%")).toBeInTheDocument();
  });

  it("tests the connection and alerts the result", async () => {
    mockPost.mockImplementation((url: string) => {
      if (url.endsWith("/test")) {
        return Promise.resolve({ data: { reachable: true, error: null } });
      }
      return Promise.resolve({ data: {} });
    });

    render(<LocalModelsPage />);
    await waitFor(() => expect(screen.getByText("My Ollama")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /^test$/i })[0]);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/local-models/p1/test");
    });
    expect(alertSpy).toHaveBeenCalledWith("✅ Connection successful!");
  });

  it("alerts a failure when the connection test fails", async () => {
    mockPost.mockRejectedValue(new Error("connection refused"));

    render(<LocalModelsPage />);
    await waitFor(() => expect(screen.getByText("My Ollama")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /^test$/i })[0]);

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("❌ Connection test failed");
    });
  });

  it("edits and saves model capabilities", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/models")) {
        return Promise.resolve({ data: { models: ["llama3:8b"] } });
      }
      if (url.includes("/capabilities")) {
        return Promise.resolve({
          data: [
            { model_id: "llama3:8b", supports_tools: false, supports_vision: false, supports_reasoning: false, quality_score: 0.5, speed_score: 0.5, context_window: 4096 },
          ],
        });
      }
      return Promise.resolve({ data: PROVIDERS });
    });
    mockPost.mockResolvedValue({ data: { success: true } });

    render(<LocalModelsPage />);
    await waitFor(() => expect(screen.getByText("My Ollama")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /discover/i })[0]);
    await waitFor(() => expect(screen.getByText("llama3:8b")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /configure/i }));
    expect(screen.getByText("Configure: llama3:8b")).toBeInTheDocument();

    // Radix checkboxes carry no accessible label, so target them by order:
    // Tools, Vision, Reasoning
    const toolsCheckbox = screen.getAllByRole("checkbox")[0];
    fireEvent.click(toolsCheckbox);
    expect(toolsCheckbox).toHaveAttribute("aria-checked", "true");

    fireEvent.change(document.querySelector('input[type="range"]')!, { target: { value: "80" } });
    fireEvent.click(screen.getByRole("button", { name: /save capabilities/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        "/api/local-models/p1/capabilities",
        expect.objectContaining({
          model_id: "llama3:8b",
          supports_tools: true,
          quality_score: 0.8,
        })
      );
    });
  });
});
