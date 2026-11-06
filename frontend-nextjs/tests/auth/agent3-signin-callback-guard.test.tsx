/**
 * Agent 3 probe — merged PR687 review (2026-11-06).
 *
 * The signin consumer guard (`/auth/signin`) is the return target of live
 * producers this PR does not touch (integration OAuth start/callback), but
 * unlike /login it had no callbackUrl twins. Pins the same contract the
 * merged PR relies on across the auth family: relative path+query honored,
 * absolute and protocol-relative (`//host`) refused to /dashboard.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useRouter } from 'next/router';
import { signIn, getSession } from 'next-auth/react';
import SignIn from '@/pages/auth/signin';
import { useToast } from '@/components/ui/use-toast';
import { loginWithBackend, persistBackendToken } from '@/lib/backendAuth';

jest.mock('next/router', () => ({
  useRouter: jest.fn(),
}));

jest.mock('next-auth/react', () => ({
  signIn: jest.fn(),
  getSession: jest.fn(),
}));

jest.mock('@/components/ui/use-toast', () => ({
  useToast: jest.fn(() => ({
    toast: jest.fn(),
  })),
}));

jest.mock('@/lib/backendAuth', () => ({
  loginWithBackend: jest.fn(),
  persistBackendToken: jest.fn(),
}));

describe('SignIn callbackUrl guard (Agent 3 probe)', () => {
  const mockPush = jest.fn(() => Promise.resolve(true));

  function renderWithQuery(query: Record<string, any>) {
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      pathname: '/auth/signin',
      query,
      isReady: true,
    });
    const { container } = render(<SignIn />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password/i), {
      target: { value: 'secret123' },
    });
    // The social buttons also match /sign in/i — target the form submit.
    const submit = container.querySelector('button[type="submit"]');
    if (!submit) throw new Error('submit button not found');
    fireEvent.click(submit);
  }

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: jest.fn() });
    (getSession as jest.Mock).mockResolvedValue(null);
    (signIn as jest.Mock).mockResolvedValue({ ok: true, error: null });
    (loginWithBackend as jest.Mock).mockResolvedValue({
      access_token: 'test-token',
      token_type: 'bearer',
    });
    (persistBackendToken as jest.Mock).mockImplementation(() => {});
  });

  test('honors a relative callbackUrl path and query', async () => {
    renderWithQuery({ callbackUrl: '/integrations/salesforce?step=2' });
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith('/integrations/salesforce?step=2'),
    );
  });

  test('refuses a protocol-relative callbackUrl to /dashboard', async () => {
    renderWithQuery({ callbackUrl: '//evil.example.com/phish' });
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard'));
    expect(mockPush).not.toHaveBeenCalledWith('//evil.example.com/phish');
  });

  test('refuses an absolute callbackUrl to /dashboard', async () => {
    renderWithQuery({ callbackUrl: 'https://evil.example.com/phish' });
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard'));
    expect(mockPush).not.toHaveBeenCalledWith('https://evil.example.com/phish');
  });
});
