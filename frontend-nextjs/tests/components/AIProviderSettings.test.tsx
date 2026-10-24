/**
 * AIProviderSettings component tests.
 *
 * Regression coverage for the BYOK settings journey: GET /api/ai/providers
 * is auth-gated AND wraps its payload in the standard ApiResponse envelope
 * ({success, data: {providers}}). The component previously read top-level
 * `providers` with no Authorization header → an error page on /settings/ai.
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getByRole("heading", { name: "OpenAI" })).toBeInTheDocument();
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

  test("shows the saved routing policy and persists a selected set", async () => {
    const policy = {
      success: true,
      data: {
        policy: {
          mode: "selected",
          allowed_providers: ["ollama"],
          preferred: { provider: "ollama", model: "llama3.1:8b" },
          source: "db",
          managed_by_env: false,
          revision: "rev-1",
          error: null,
          scope: "installation",
        },
      },
    };
    (global.fetch as jest.Mock) = jest.fn((url: string, init?: any) => {
      if (String(url).includes("/ai/provider-policy")) {
        if (init?.method === "PUT") {
          return Promise.resolve({ ok: true, json: async () => policy });
        }
        return Promise.resolve({ ok: true, json: async () => policy });
      }
      if (String(url).includes("/ai/providers")) {
        return Promise.resolve({ ok: true, json: async () => WRAPPED });
      }
      return Promise.resolve({ ok: true, json: async () => ({ api_key: "sat" }) });
    });

    renderSettings();

    expect(
      await screen.findByText("Where Atom may send requests")
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Only selected providers/i)).toBeChecked();
    expect(screen.getByText("Key saved — not checked")).toBeInTheDocument();

    const save = screen.getByRole("button", {
      name: /Save Routing Policy/i,
    });
    save.click();
    await waitFor(() => {
      const put = (global.fetch as jest.Mock).mock.calls.find(
        ([url, init]: [string, any]) =>
          String(url).includes("/ai/provider-policy") && init?.method === "PUT"
      );
      expect(put).toBeTruthy();
      const body = JSON.parse(put[1].body);
      expect(body.mode).toBe("selected");
      expect(body.allowed_providers).toContain("ollama");
    });
  });

  test("shows authentication failure, not a generic working badge", async () => {
    const checked = {
      ...WRAPPED,
      data: {
        ...WRAPPED.data,
        providers: WRAPPED.data.providers.map((p: any) => p.provider.id === "openai"
          ? {
              ...p,
              usage: {
                last_check_at: "2026-10-24T12:00:00Z",
                last_check_ok: false,
                last_check_status: "authentication_failed",
                last_check_message: "The provider rejected the saved credential.",
              },
            }
          : p),
      },
    };
    (global.fetch as jest.Mock) = jest.fn((url: string) => {
      if (String(url).includes("/ai/provider-policy")) {
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      }
      if (String(url).includes("/ai/providers")) {
        return Promise.resolve({ ok: true, json: async () => checked });
      }
      return Promise.resolve({ ok: true, json: async () => ({ api_key: "sat" }) });
    });

    renderSettings();

    expect(
      await screen.findByText("Authentication failed")
    ).toBeInTheDocument();
    expect(
      screen.getByText("The provider rejected the saved credential.")
    ).toBeInTheDocument();
    expect(screen.queryByText("✓ Working")).not.toBeInTheDocument();
  });

  test("failed policy save restores the prior effective controls", async () => {
    const policy = {
      success: true,
      data: {
        policy: {
          mode: "selected",
          allowed_providers: ["ollama"],
          preferred: null,
          source: "db",
          managed_by_env: false,
          revision: "rev-1",
          error: null,
          scope: "installation",
        },
      },
    };
    (global.fetch as jest.Mock) = jest.fn((url: string, init?: any) => {
      if (String(url).includes("/ai/provider-policy")) {
        if (init?.method === "PUT") {
          return Promise.resolve({
            ok: false,
            status: 400,
            json: async () => ({ detail: "Preferred provider must be in the allowed set." }),
          });
        }
        return Promise.resolve({ ok: true, json: async () => policy });
      }
      if (String(url).includes("/ai/providers")) {
        return Promise.resolve({ ok: true, json: async () => WRAPPED });
      }
      return Promise.resolve({ ok: true, json: async () => ({ api_key: "sat" }) });
    });

    renderSettings();
    await screen.findByText("Where Atom may send requests");
    fireEvent.click(screen.getByLabelText(/Automatic among enabled providers/i));
    fireEvent.click(screen.getByRole("button", { name: /Save Routing Policy/i }));

    await screen.findByText(/Preferred provider must be in the allowed set/i);
    expect(screen.getByLabelText(/Only selected providers/i)).toBeChecked();
    expect(screen.getByLabelText(/Automatic among enabled providers/i)).not.toBeChecked();
  });

  test("a stale check cannot show Ready after the key is gone", async () => {
    const noKey = {
      ...WRAPPED,
      data: {
        ...WRAPPED.data,
        providers: WRAPPED.data.providers.map((p: any) => p.provider.id === "openai"
          ? {
              ...p,
              has_api_keys: false,
              status: "inactive",
              usage: {
                last_check_at: "2026-10-24T12:00:00Z",
                last_check_ok: true,
                last_check_status: "ready",
                last_check_message: "Provider answered.",
              },
            }
          : p),
      },
    };
    (global.fetch as jest.Mock) = jest.fn((url: string) => {
      if (String(url).includes("/ai/provider-policy")) {
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      }
      if (String(url).includes("/ai/providers")) {
        return Promise.resolve({ ok: true, json: async () => noKey });
      }
      return Promise.resolve({ ok: true, json: async () => ({ api_key: "sat" }) });
    });

    renderSettings();
    await screen.findByRole("heading", { name: "OpenAI" });
    expect(screen.getAllByText("Not configured").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Ready — checked/i)).not.toBeInTheDocument();
  });

  test("environment-managed policy disables conflicting controls", async () => {
    const managed = {
      success: true,
      data: {
        policy: {
          mode: "selected",
          allowed_providers: ["ollama"],
          preferred: null,
          source: "env",
          managed_by_env: true,
          revision: "rev-env",
          error: null,
          scope: "installation",
        },
      },
    };
    (global.fetch as jest.Mock) = jest.fn((url: string) => {
      if (String(url).includes("/ai/provider-policy")) {
        return Promise.resolve({ ok: true, json: async () => managed });
      }
      if (String(url).includes("/ai/providers")) {
        return Promise.resolve({ ok: true, json: async () => WRAPPED });
      }
      return Promise.resolve({ ok: true, json: async () => ({ api_key: "sat" }) });
    });

    renderSettings();

    expect(
      await screen.findByText(/Managed by this installation/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Save Routing Policy/i })
    ).toBeDisabled();
    expect(screen.getByLabelText(/Only selected providers/i)).toBeDisabled();
  });
});
