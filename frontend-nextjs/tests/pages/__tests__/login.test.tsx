/**
 * LoginPage Tests (pages/login.tsx)
 *
 * Verifies REAL login page behavior:
 * - Login submit → backend auth → token persisted → redirect (default /dashboard)
 * - callbackUrl honored; open-redirect (external URL) falls back to /dashboard
 * - Login failure → error message rendered, no redirect
 * - Network error → error message rendered
 * - Register mode toggle → first/last name inputs, register submit + failure
 * - Password visibility toggle, loading state on submit button
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import LoginPage from '@/pages/login';

const mockPush = jest.fn(() => Promise.resolve(true));
let mockQuery: Record<string, any> = {};

jest.mock('next/router', () => ({
  useRouter: () => ({
    route: '/login',
    pathname: '/login',
    query: mockQuery,
    asPath: '/login',
    isReady: true,
    push: mockPush,
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  }),
}));

const mockFetch = jest.fn();
let setItemSpy: jest.SpyInstance;
let removeItemSpy: jest.SpyInstance;

const okResponse = (body: any) => ({
  ok: true,
  status: 200,
  json: async () => body,
});
const errorResponse = (detail: string) => ({
  ok: false,
  status: 401,
  json: async () => ({ detail }),
});

const fillLoginForm = (email: string, password: string) => {
  fireEvent.change(screen.getByTestId('login-email-input'), { target: { value: email } });
  fireEvent.change(screen.getByTestId('login-password-input'), { target: { value: password } });
};

const switchToRegisterMode = () => {
  fireEvent.click(screen.getByTestId('login-toggle-mode'));
  fireEvent.change(screen.getByTestId('login-first-name-input'), { target: { value: 'Jane' } });
  fireEvent.change(screen.getByTestId('login-last-name-input'), { target: { value: 'Doe' } });
  // The register handler requires password confirmation to match before it
  // will call the backend.
  fireEvent.change(screen.getByTestId('login-confirm-password-input'), { target: { value: 'secret123' } });
};

describe('LoginPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockQuery = {};
    global.fetch = mockFetch as any;
    // jsdom localStorage is the real Storage in this env (the setup.ts mock
    // assignment does not stick), so spy on the prototype — same pattern as
    // tests/pages/__tests__/settings-account.test.tsx.
    setItemSpy = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
    removeItemSpy = jest.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {});
    mockPush.mockResolvedValue(true);
  });

  test('renders login form with ATOM Platform header and default mode', () => {
    render(<LoginPage />);
    expect(screen.getByText('ATOM Platform')).toBeInTheDocument();
    expect(screen.getByText('Welcome back!')).toBeInTheDocument();
    expect(screen.getByTestId('login-email-input')).toBeInTheDocument();
    expect(screen.getByTestId('login-password-input')).toBeInTheDocument();
    expect(screen.getByTestId('login-submit-button')).toHaveTextContent('Sign In');
    expect(screen.queryByTestId('login-first-name-input')).not.toBeInTheDocument();
  });

  test('successful login persists token and redirects to /dashboard by default', async () => {
    mockFetch.mockResolvedValue(okResponse({ access_token: 'jwt-token-123' }));
    render(<LoginPage />);
    fillLoginForm('user@example.com', 'secret123');
    fireEvent.click(screen.getByTestId('login-submit-button'));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard'));

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ username: 'user@example.com', password: 'secret123' }),
      })
    );
    expect(setItemSpy).toHaveBeenCalledWith('auth_token', 'jwt-token-123');
    expect(setItemSpy).toHaveBeenCalledWith('token', 'jwt-token-123');
    expect(removeItemSpy).toHaveBeenCalledWith('atom_explicit_logout');
  });

  test('redirects to callbackUrl when present', async () => {
    mockQuery = { callbackUrl: '/workflows/123' };
    mockFetch.mockResolvedValue(okResponse({ access_token: 'tok' }));
    render(<LoginPage />);
    fillLoginForm('user@example.com', 'secret123');
    fireEvent.click(screen.getByTestId('login-submit-button'));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/workflows/123'));
  });

  test('blocks open redirect for external callbackUrl', async () => {
    mockQuery = { callbackUrl: 'https://evil.example.com/phish' };
    mockFetch.mockResolvedValue(okResponse({ access_token: 'tok' }));
    render(<LoginPage />);
    fillLoginForm('user@example.com', 'secret123');
    fireEvent.click(screen.getByTestId('login-submit-button'));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard'));
  });

  test('blocks protocol-relative callbackUrl', async () => {
    mockQuery = { callbackUrl: '//evil.example.com/phish' };
    mockFetch.mockResolvedValue(okResponse({ access_token: 'tok' }));
    render(<LoginPage />);
    fillLoginForm('user@example.com', 'secret123');
    fireEvent.click(screen.getByTestId('login-submit-button'));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard'));
  });

  test('shows error message when login fails with backend detail', async () => {
    mockFetch.mockResolvedValue(errorResponse('Invalid email or password'));
    render(<LoginPage />);
    fillLoginForm('user@example.com', 'wrong');
    fireEvent.click(screen.getByTestId('login-submit-button'));

    await waitFor(() => {
      expect(screen.getByTestId('login-error-message')).toHaveTextContent('Invalid email or password');
    });
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('shows generic error when login throws (network failure)', async () => {
    mockFetch.mockRejectedValue(new Error('Network Error'));
    render(<LoginPage />);
    fillLoginForm('a@example.com', 'secret123');
    fireEvent.click(screen.getByTestId('login-submit-button'));

    // loginWithBackend maps raw network errors ("Failed to fetch") to a
    // user-friendly message instead of surfacing them verbatim.
    await waitFor(() => {
      expect(screen.getByTestId('login-error-message')).toHaveTextContent(
        'Unable to connect to the server. Please check your internet connection and try again.'
      );
    });
  });

  test('disables submit button and shows Processing... while loading', async () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<LoginPage />);
    fillLoginForm('user@example.com', 'secret123');
    fireEvent.click(screen.getByTestId('login-submit-button'));

    const button = screen.getByTestId('login-submit-button');
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent('Processing...');
  });

  test('password visibility toggle switches input type', () => {
    render(<LoginPage />);
    const passwordInput = screen.getByTestId('login-password-input');
    expect(passwordInput).toHaveAttribute('type', 'password');

    fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(passwordInput).toHaveAttribute('type', 'text');

    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  test('toggles to register mode revealing first/last name inputs', () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByTestId('login-toggle-mode'));

    expect(screen.getByText('Create your account')).toBeInTheDocument();
    expect(screen.getByTestId('login-first-name-input')).toBeInTheDocument();
    expect(screen.getByTestId('login-last-name-input')).toBeInTheDocument();
    expect(screen.getByTestId('login-submit-button')).toHaveTextContent('Create Account');

    fireEvent.click(screen.getByTestId('login-toggle-mode'));
    expect(screen.getByText('Welcome back!')).toBeInTheDocument();
    expect(screen.queryByTestId('login-first-name-input')).not.toBeInTheDocument();
  });

  test('successful register persists token and redirects', async () => {
    mockFetch.mockResolvedValue(okResponse({ access_token: 'reg-token' }));
    render(<LoginPage />);
    switchToRegisterMode();

    fireEvent.change(screen.getByTestId('login-email-input'), { target: { value: 'jane@example.com' } });
    fireEvent.change(screen.getByTestId('login-password-input'), { target: { value: 'secret123' } });
    fireEvent.click(screen.getByTestId('login-submit-button'));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard'));

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/auth/register',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          email: 'jane@example.com',
          password: 'secret123',
          first_name: 'Jane',
          last_name: 'Doe',
        }),
      })
    );
    expect(setItemSpy).toHaveBeenCalledWith('auth_token', 'reg-token');
  });

  test('shows backend detail when registration fails', async () => {
    mockFetch.mockResolvedValue(errorResponse('Email already registered'));
    render(<LoginPage />);
    switchToRegisterMode();
    fireEvent.change(screen.getByTestId('login-email-input'), { target: { value: 'taken@example.com' } });
    fireEvent.change(screen.getByTestId('login-password-input'), { target: { value: 'secret123' } });
    fireEvent.click(screen.getByTestId('login-submit-button'));

    await waitFor(() => {
      // lib/registration maps duplicate-email details to a friendlier,
      // actionable message rather than passing the raw backend text through.
      expect(screen.getByTestId('login-error-message')).toHaveTextContent(
        'An account with this email already exists. Try signing in instead.'
      );
    });
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('shows fallback message when registration error has no detail', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
    render(<LoginPage />);
    switchToRegisterMode();
    fireEvent.change(screen.getByTestId('login-email-input'), { target: { value: 'a@b.com' } });
    fireEvent.change(screen.getByTestId('login-password-input'), { target: { value: 'secret123' } });
    fireEvent.click(screen.getByTestId('login-submit-button'));

    await waitFor(() => {
      expect(screen.getByTestId('login-error-message')).toHaveTextContent('Failed to create account. Please try again.');
    });
  });

  test('toggling mode clears a previously shown error', () => {
    mockFetch.mockResolvedValue(errorResponse('Invalid email or password'));
    render(<LoginPage />);
    fillLoginForm('user@example.com', 'wrong');
    fireEvent.click(screen.getByTestId('login-submit-button'));

    return waitFor(() => {
      expect(screen.getByTestId('login-error-message')).toBeInTheDocument();
    }).then(() => {
      fireEvent.click(screen.getByTestId('login-toggle-mode'));
      expect(screen.queryByTestId('login-error-message')).not.toBeInTheDocument();
    });
  });
});
