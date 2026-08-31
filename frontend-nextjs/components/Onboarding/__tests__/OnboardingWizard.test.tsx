/**
 * OnboardingWizard component tests.
 *
 * Covers the 4-step flow: Welcome → Profile → Connect (Ollama probe + API key
 * cards) → Ready, plus onboarding completion and failure surfaces.
 * fetch is mocked per-test; the toast hook is mocked to record calls.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { OnboardingWizard } from '../OnboardingWizard';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] as any[] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const API_BASE = 'http://localhost:8000';

const mockOnUpdate = jest.fn();
const mockOnClose = jest.fn();

interface RouteMock {
  match: string;
  res: () => { ok: boolean; status?: number; json?: any };
}

const mockFetch = (routes: RouteMock[]) => {
  (global.fetch as jest.Mock) = jest.fn((url: string) => {
    const route = routes.find((r) => String(url).includes(r.match));
    const r = route ? route.res() : { ok: false, status: 404, json: {} };
    return Promise.resolve({
      ok: r.ok,
      status: r.status ?? 200,
      json: async () => r.json ?? {},
    });
  });
};

const renderWizard = (user: any = { first_name: 'Ada' }) => {
  return render(
    <OnboardingWizard isOpen onClose={mockOnClose} user={user} onUpdate={mockOnUpdate} />
  );
};

describe('OnboardingWizard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch([
      { match: '/api/onboarding/probe-ollama', res: () => ({ ok: false, status: 200 }) },
    ]);
  });

  it('renders the welcome step with the user first name', () => {
    renderWizard();
    expect(screen.getByRole('heading', { name: /Welcome to Atom/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Hello, Ada!/i })).toBeInTheDocument();
  });

  it('falls back to a generic greeting without a first name', () => {
    renderWizard({});
    expect(screen.getByRole('heading', { name: /Hello, there!/i })).toBeInTheDocument();
  });

  it('walks through Profile and Connect steps and prefills the role', async () => {
    renderWizard({ first_name: 'Ada', specialty: 'Developer' });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    expect(screen.getByText('Tell us about yourself')).toBeInTheDocument();
    expect((screen.getByLabelText(/primary role/i) as HTMLInputElement).value).toBe('Developer');

    fireEvent.change(screen.getByLabelText(/primary role/i), { target: { value: 'Marketer' } });
    fireEvent.change(screen.getByLabelText(/automate first/i), { target: { value: 'Lead processing' } });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    expect(screen.getByText('Connect Your Intelligence')).toBeInTheDocument();
  });

  it('keeps the Back button hidden on the first step and functional later', () => {
    renderWizard();
    const back = screen.getByRole('button', { name: /Back/i });
    expect(back).toBeDisabled();
    expect(back.className).toContain('invisible');

    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Back/i }));
    expect(screen.getByRole('heading', { name: /Hello, Ada!/i })).toBeInTheDocument();
  });

  it('probes Ollama on the Connect step and shows the 1-click enable card when detected', async () => {
    mockFetch([
      {
        match: '/api/onboarding/probe-ollama',
        res: () => ({ ok: true, json: { data: { reachable: true } } }),
      },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    expect(await screen.findByText('Detected')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Enable Ollama/i })
    ).toBeInTheDocument();
  });

  it('enables Ollama, toasts success, updates the user and advances to Ready', async () => {
    mockFetch([
      {
        match: '/api/onboarding/probe-ollama',
        res: () => ({ ok: true, json: { data: { reachable: true } } }),
      },
      { match: '/api/ai/providers/ollama/keys', res: () => ({ ok: true, json: {} }) },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    fireEvent.click(await screen.findByRole('button', { name: /Enable Ollama/i }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Ollama connected', variant: 'success' })
      );
    });
    expect(mockOnUpdate).toHaveBeenCalledWith({
      onboarding_completed: false,
      provider_configured: 'ollama',
    });
    expect(screen.getByRole('heading', { name: /You're Ready!/i })).toBeInTheDocument();

    const post = (global.fetch as jest.Mock).mock.calls.find(
      ([url]: [string, RequestInit?]) => String(url).includes('/api/ai/providers/ollama/keys')
    );
    expect(post).toBeDefined();
    expect(JSON.parse(post[1].body)).toEqual(
      expect.objectContaining({ api_key: 'ollama-local-no-key-required' })
    );
  });

  it('shows install instructions when Ollama is not reachable', async () => {
    mockFetch([
      {
        match: '/api/onboarding/probe-ollama',
        res: () => ({ ok: true, json: { data: { reachable: false, install_url: 'https://ollama.test/dl' } } }),
      },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    expect(
      await screen.findByText('Ollama not detected on this machine.')
    ).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /Install Ollama/i });
    expect(link).toHaveAttribute('href', 'https://ollama.test/dl');
  });

  it('keeps the save-key button disabled until the key is at least 10 characters', () => {
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    const keyInput = screen.getByPlaceholderText('sk-...');
    fireEvent.change(keyInput, { target: { value: 'short' } });
    expect(screen.getByRole('button', { name: /Save key & continue/i })).toBeDisabled();

    fireEvent.change(keyInput, { target: { value: 'sk-1234567890' } });
    expect(screen.getByRole('button', { name: /Save key & continue/i })).toBeEnabled();
  });

  it('saves a valid API key for the selected provider and advances to Ready', async () => {
    mockFetch([
      { match: '/api/ai/providers/anthropic/keys', res: () => ({ ok: true, json: {} }) },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'anthropic' } });
    fireEvent.change(screen.getByPlaceholderText('sk-ant-...'), {
      target: { value: 'sk-ant-1234567890' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Save key & continue/i }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'API key saved' })
      );
    });
    expect(mockOnUpdate).toHaveBeenCalledWith({
      onboarding_completed: false,
      provider_configured: 'anthropic',
    });
    expect(screen.getByRole('heading', { name: /You're Ready!/i })).toBeInTheDocument();

    const post = (global.fetch as jest.Mock).mock.calls.find(
      ([url]: [string, RequestInit?]) => String(url).includes('/api/ai/providers/anthropic/keys')
    );
    expect(post).toBeDefined();
    expect(JSON.parse(post[1].body)).toEqual(
      expect.objectContaining({ api_key: 'sk-ant-1234567890' })
    );
  });

  it('toasts an error when saving the API key fails', async () => {
    mockFetch([
      {
        match: '/api/ai/providers/openai/keys',
        res: () => ({ ok: false, status: 500, json: { detail: 'backend exploded' } }),
      },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    fireEvent.change(screen.getByPlaceholderText('sk-...'), {
      target: { value: 'sk-1234567890' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Save key & continue/i }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to save key', variant: 'error' })
      );
    });
    // Still on the Connect step — no advance.
    expect(screen.getByText('Connect Your Intelligence')).toBeInTheDocument();
  });

  it('completes onboarding, calls onUpdate and closes the dialog', async () => {
    mockFetch([
      { match: '/api/onboarding/update', res: () => ({ ok: true, json: {} }) },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    expect(screen.getByRole('heading', { name: /You're Ready!/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Start Automating/i }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "You're all set!" })
      );
    });
    expect(mockOnUpdate).toHaveBeenCalledWith({ onboarding_completed: true });
    expect(mockOnClose).toHaveBeenCalledTimes(1);

    const post = (global.fetch as jest.Mock).mock.calls.find(
      ([url]: [string, RequestInit?]) => String(url).includes('/api/onboarding/update')
    );
    expect(JSON.parse(post[1].body)).toEqual({ completed: true, step: 'completed' });
  });

  it('surfaces a failure when the onboarding update is rejected', async () => {
    mockFetch([
      { match: '/api/onboarding/update', res: () => ({ ok: false, status: 401, json: {} }) },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Start Automating/i }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Could not complete onboarding', variant: 'destructive' })
      );
    });
    expect(mockOnClose).not.toHaveBeenCalled();
    expect(mockOnUpdate).not.toHaveBeenCalledWith({ onboarding_completed: true });
  });

  it('populates the provider dropdown from the live registry and excludes Ollama', async () => {
    mockFetch([
      {
        match: '/api/onboarding/probe-ollama',
        res: () => ({ ok: true, json: { data: { reachable: false } } }),
      },
      {
        // Tenant-scoped BYOK registry, wrapped in the ApiResponse envelope.
        match: '/api/ai/providers',
        res: () => ({
          ok: true,
          json: {
            success: true,
            data: {
              providers: [
                { provider: { id: 'openai', name: 'OpenAI' }, has_api_keys: true, status: 'active' },
                { provider: { id: 'openrouter', name: 'OpenRouter' }, has_api_keys: false, status: 'inactive' },
                { provider: { id: 'moonshot', name: 'Moonshot AI (Kimi)' }, has_api_keys: false, status: 'inactive' },
                { provider: { id: 'ollama', name: 'Ollama' }, has_api_keys: false, status: 'inactive' },
              ],
              total_providers: 4,
            },
          },
        }),
      },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    const select = await screen.findByRole('combobox');
    // The live registry fetch resolves after the seed list renders — wait for
    // the options to swap.
    await waitFor(() => {
      const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
      expect(options).toContain('openrouter');
      expect(options).toContain('moonshot');
    });
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
    expect(options).not.toContain('ollama'); // Card A owns the Ollama path
  });

  it('falls back to the seeded provider list when the registry fetch fails', async () => {
    mockFetch([
      {
        match: '/api/onboarding/probe-ollama',
        res: () => ({ ok: false, status: 200 }),
      },
      { match: '/api/ai/providers', res: () => ({ ok: false, status: 401, json: {} }) },
    ]);
    renderWizard();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    const select = await screen.findByRole('combobox');
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
    expect(options).toEqual(
      expect.arrayContaining(['openai', 'openrouter', 'anthropic', 'deepseek', 'glm'])
    );
  });
});
