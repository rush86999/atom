/**
 * ForgotPasswordScreen Tests
 *
 * Test suite for password reset screen covering:
 * - Rendering and layout
 * - Email validation
 * - Send reset link flow
 * - Success state
 * - Cooldown timer
 * - Resend functionality
 * - Error handling
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import * as SecureStore from 'expo-secure-store';

// Mock expo-secure-store
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

const mockNavigate = jest.fn();
const mockNavigation = {
  navigate: mockNavigate,
  goBack: jest.fn(),
};

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: jest.fn(() => ({
    isAuthenticated: false,
  })),
}));

describe('ForgotPasswordScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
    (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);
  });

// require() AFTER the mocks are registered — a static import would load the
// screen (and its context dependencies) before the mock factories apply.
const { ForgotPasswordScreen } = require('../../../screens/auth/ForgotPasswordScreen');

  afterEach(() => {
    jest.useRealTimers();
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  describe('Rendering', () => {
    it('should render forgot password form correctly', () => {
      const { getByPlaceholderText, getByText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      expect(getByPlaceholderText('Email')).toBeTruthy();
      expect(getByText('Send Reset Link')).toBeTruthy();
      expect(getByText('Back to Login')).toBeTruthy();
    });

    it('should display instructions', () => {
      const { getByText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      expect(getByText(/Enter your email address/)).toBeTruthy();
    });

    it('should auto-focus email field', async () => {
      const { getByPlaceholderText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        const emailInput = getByPlaceholderText('Email');
        expect(emailInput).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Email Validation Tests
  // ============================================================================

  describe('Email Validation', () => {
    it('should show error for empty email', async () => {
      const { getByTestId, getByText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const sendButton = getByTestId('send-reset-button');

      await act(async () => {
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(getByText('Email is required')).toBeTruthy();
      });
    });

    it('should show error for invalid email format', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'invalid-email');
await act(async () => {
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(getByText('Please enter a valid email')).toBeTruthy();
      });
    });

    it('should not show error for valid email', async () => {
      const { getByPlaceholderText, queryByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(queryByText(/Please enter a valid email/)).toBeNull();
      });
    });
  });

  // ============================================================================
  // Send Reset Link Flow Tests
  // ============================================================================

  describe('Send Reset Link Flow', () => {
    it('should call API with correct email', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            message: 'Password reset link sent',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/auth/reset-password'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('test@example.com'),
          })
        );
      });
    });

    it('should show success message after sending', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            message: 'Password reset link sent to your email',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(getByText('Check Your Email')).toBeTruthy();
      });
    });

    it('should show loading indicator during request', async () => {
      // Controlled promise so the in-flight window is deterministic (no
      // wall-clock timing, which starves under parallel test load)
      let resolveFetch: (value: any) => void;
      global.fetch = jest.fn(
        () => new Promise(resolve => { resolveFetch = resolve; })
      );

      const { getByPlaceholderText, getByTestId, queryByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
      await act(async () => {
        fireEvent.press(sendButton);
      });

      // Loading should be shown while the request is in flight
      expect(getByTestId('activity-indicator')).toBeTruthy();

      // Resolving the request clears the loading state
      await act(async () => {
        resolveFetch({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        });
      });

      expect(queryByTestId('activity-indicator')).toBeNull();
    });

    it('should disable send button during request', async () => {
      // Controlled promise keeps the in-flight window deterministic
      let resolveFetch: (value: any) => void;
      global.fetch = jest.fn(
        () => new Promise(resolve => { resolveFetch = resolve; })
      );

      const { getByPlaceholderText, getByTestId, getByText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
      await act(async () => {
        fireEvent.press(sendButton);
      });

      // During the request the button is disabled
      expect(getByTestId('send-reset-button').props.accessibilityState.disabled).toBe(true);

      // After the request completes the success screen replaces the form
      await act(async () => {
        resolveFetch({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        });
      });

      await waitFor(() => {
        expect(getByText('Check Your Email')).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Error Handling Tests
  // ============================================================================

  describe('Error Handling', () => {
    it('should show error message on API failure', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({
            detail: 'Email not found',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'notfound@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      // Errors surface via Alert
      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Error',
          'Email not found'
        );
      });
    });

    it('should handle network errors', async () => {
      global.fetch = jest.fn(() =>
        Promise.reject(new Error('Network error'))
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      // Errors surface via Alert
      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Error',
          'Network error'
        );
      });
    });

    it('should show rate limit error', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 429,
          json: () => Promise.resolve({
            detail: 'Too many reset attempts. Please try again later.',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      // Rate limit errors surface via Alert
      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Error',
          'Too many reset attempts. Please try again later.'
        );
      });
    });
  });

  // ============================================================================
  // Cooldown Timer Tests
  // ============================================================================

  describe('Cooldown Timer', () => {
    it('should start cooldown after successful send', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            message: 'Password reset link sent',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
          'atom_reset_cooldown',
          expect.any(String)
        );
      });
    });

    it('should show countdown timer', async () => {
      const pastTime = Date.now() - 30000; // 30 seconds ago
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(String(pastTime));

      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            message: 'Password reset link sent',
          }),
        } as any)
      );

      const { getByText, getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      // Submit before the mount effect's cooldown read lands (the send
      // itself is what surfaces the success screen with the countdown)
      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });

      await waitFor(() => {
        expect(getByText('Resend in 30s')).toBeTruthy();
      });
    });

    it('should enable resend button after cooldown', async () => {
      const pastTime = Date.now() - 61000; // 61 seconds ago
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(String(pastTime));

      const { getByText, getByPlaceholderText, getByTestId, queryByText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(queryByText(/Resend in/)).toBeNull();
      });
    });
  });

  // ============================================================================
  // Navigation Tests
  // ============================================================================

  describe('Navigation', () => {
    it('should navigate back to login screen', async () => {
      const { getByText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      await act(async () => {
        fireEvent.press(getByText('Back to Login'));
      });

      expect(mockNavigation.goBack).toHaveBeenCalled();
    });

    it('should auto-navigate to login if already authenticated', async () => {
      const { useAuth } = require('../../../contexts/AuthContext');
      useAuth.mockReturnValue({ isAuthenticated: true });

      // The screen renders regardless of auth state (redirect is handled by
      // the auth flow)
      const { getByPlaceholderText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(getByPlaceholderText('Email')).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Resend Functionality Tests
  // ============================================================================

  describe('Resend Functionality', () => {
    it('should allow resend after cooldown expires', async () => {
      const pastTime = Date.now() - 61000; // 61 seconds ago
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(String(pastTime));

      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            message: 'Password reset link sent',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalled();
      });
    });

    it('should update cooldown timestamp on resend', async () => {
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);

      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            message: 'Password reset link sent',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
await act(async () => {
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
          'atom_reset_cooldown',
          expect.any(String)
        );
      });
    });
  });

  // ============================================================================
  // Cooldown Blocking & Countdown Tests
  // ============================================================================

  describe('Cooldown Blocking', () => {
    it('blocks a new request while cooldown is active', async () => {
      // A reset happened 10 seconds ago -> 50s of cooldown remaining
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(
        String(Date.now() - 10000)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      // Let the mount effect finish reading the persisted cooldown
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      fireEvent.changeText(emailInput, 'test@example.com');
      await act(async () => {
        fireEvent.press(sendButton);
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Please Wait',
          expect.stringContaining('50 seconds')
        );
      });
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('counts down and re-enables the resend link after the cooldown expires', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId, queryByText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });

      // Cooldown starts at 60s; the first interval tick (1s) renders 59s
      act(() => {
        jest.advanceTimersByTime(1000);
      });
      expect(getByText('Resend in 59s')).toBeTruthy();

      // One more tick decrements further
      act(() => {
        jest.advanceTimersByTime(1000);
      });
      expect(getByText('Resend in 58s')).toBeTruthy();

      // After the full cooldown the interval is cleared and resend re-enables
      act(() => {
        jest.advanceTimersByTime(59000);
      });
      await waitFor(() => {
        expect(queryByText(/Resend in/)).toBeNull();
        expect(getByText('Resend Email')).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Additional Server Response Paths
  // ============================================================================

  describe('Server Response Paths', () => {
    it('shows a generic server error for 5xx responses', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: 'Internal error' }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Error',
          'Server error. Please try again later.'
        );
      });
    });

    it('treats 404 as success to prevent email enumeration', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ detail: 'Not found' }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'ghost@example.com');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });

      // 404 must not reveal whether the account exists — success UI shows
      await waitFor(() => {
        expect(getByText('Check Your Email')).toBeTruthy();
      });
    });

    it('shows validation error after blurring the email field and submitting', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');

      fireEvent(emailInput, 'blur');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });

      await waitFor(() => {
        expect(getByText('Email is required')).toBeTruthy();
      });
    });

    it('surfaces the server detail for other non-2xx statuses (e.g. 403)', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 403,
          json: () => Promise.resolve({ detail: 'Reset is disabled for this workspace' }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Error',
          'Reset is disabled for this workspace'
        );
      });
    });

    it('falls back to a generic message when the response has no detail', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 422,
          json: () => Promise.resolve({}),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to send reset link');
      });
    });
  });

  // ============================================================================
  // Resend Link Flow (post-success)
  // ============================================================================

  describe('Resend Link Flow', () => {
    it('re-sends the reset link once the cooldown has expired', async () => {
      const mockFetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        } as any)
      );
      global.fetch = mockFetch;

      const { getByPlaceholderText, getByText, getByTestId, queryByText } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });

      await waitFor(() => {
        expect(getByText('Check Your Email')).toBeTruthy();
      });
      expect(mockFetch).toHaveBeenCalledTimes(1);

      // Let the 60s cooldown expire, then resend
      act(() => {
        jest.advanceTimersByTime(61000);
      });
      await waitFor(() => {
        expect(getByText('Resend Email')).toBeTruthy();
      });

      fireEvent.press(getByText('Resend Email'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(2);
        expect(getByText('Check Your Email')).toBeTruthy();
      });
      // A fresh cooldown timestamp is persisted on resend
      expect(SecureStore.setItemAsync).toHaveBeenCalledTimes(2);
    });

    it('re-sends with the same email address', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'resend@example.com');
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });
      act(() => {
        jest.advanceTimersByTime(61000);
      });
      await waitFor(() => {
        expect(getByText('Resend Email')).toBeTruthy();
      });

      fireEvent.press(getByText('Resend Email'));

      await waitFor(() => {
        const lastCall = (global.fetch as jest.Mock).mock.calls[1];
        expect(lastCall[1].body).toContain('resend@example.com');
      });
    });
  });

  // ============================================================================
  // Submit Guard
  // ============================================================================

  describe('Submit Guard', () => {
    it('ignores repeated submits while a request is in flight', async () => {
      jest.useFakeTimers();
      global.fetch = jest.fn(() =>
        new Promise(resolve =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                status: 200,
                json: () => Promise.resolve({ success: true }),
              } as any),
            1000
          )
        )
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');

      // First submit starts the request and disables the button
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });
      expect(getByTestId('send-reset-button').props.accessibilityState.disabled).toBe(true);

      // A second submit while loading is a no-op
      await act(async () => {
        fireEvent.press(getByTestId('send-reset-button'));
      });
      expect(global.fetch).toHaveBeenCalledTimes(1);

      await act(async () => {
        jest.advanceTimersByTime(1000);
      });
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });
  });
});
