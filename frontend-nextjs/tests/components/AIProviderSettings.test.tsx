/**
 * AIProviderSettings component tests.
 *
 * Regression coverage for the BYOK settings journey: GET /api/ai/providers
 * is auth-gated AND wraps its payload in the standard ApiResponse envelope
 * ({success, data: {providers}}). The component previously read top-level
 * `providers` with no Authorization header → an error page on /settings/ai.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import AIProviderSettings from "@/src/components/AIProviders/AIProviderSettings";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: jest.fn(), dismiss: jest.fn(), toasts: [] }),
}));

const WRAPPED = {
  success: true,
  data: {
    providers: [
      {
        provider: {
          id: "openrouter",
          name: "OpenRouter",
          description: "Unified LLM gateway",
          base_url: "https://openrouter.ai",
          supported_tasks: ["general", "reasoning"],
          model: "auto",
        },
        has_api_keys: false,
        status: "inactive",
        usage: {},
      },
      {
        provider: {
          id: "openai",
          name: "OpenAI",
          description: "GPT models",
          base_url: null,
          supported_tasks: ["general"],
          model: "gpt-5.3",
        },
        has_api_keys: true,
        status: "active",
        usage: {},
      },
    ],
    total_providers: 2,
  },
};

const renderSettings = () => render(<AIProviderSettings baseApiUrl="/api" />);

describe("AIProviderSettings", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.localStorage.setItem("token", "jwt-123");
  });

  test("renders provider cards from the ApiResponse envelope", async () => {
    (global.fetch as jest.Mock) = jest.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () =>
          String(url).includes("/ai/providers") ? WRAPPED : { api_key: "sat" },
      })
    );

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText("OpenRouter")).toBeInTheDocument();
    });
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // Available stat
  });

  test("sends the Authorization header on the providers fetch", async () => {
    (global.fetch as jest.Mock) = jest.fn(() =>
      Promise.resolve({ ok: true, json: async () => WRAPPED })
    );

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText("OpenRouter")).toBeInTheDocument();
    });
    const call = (global.fetch as jest.Mock).mock.calls.find(([url]: [string]) =>
      String(url).includes("/ai/providers")
    );
    expect(call[1].headers.Authorization).toBe("Bearer jwt-123");
  });

  test("still renders when the backend returns the legacy unwrapped shape", async () => {
    (global.fetch as jest.Mock) = jest.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () =>
          String(url).includes("/ai/providers") ? WRAPPED.data : { api_key: "sat" },
      })
    );

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText("OpenRouter")).toBeInTheDocument();
    });
  });

  test("surfaces the load error with a retry when the fetch fails", async () => {
    (global.fetch as jest.Mock) = jest.fn(() =>
      Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
    );

    renderSettings();

    expect(
      await screen.findByText("Failed to load AI providers")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
