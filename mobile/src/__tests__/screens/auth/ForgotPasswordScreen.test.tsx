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
import { ForgotPasswordScreen } from '../../../../screens/auth/ForgotPasswordScreen';

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

jest.mock('../../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: false,
  }),
}));

describe('ForgotPasswordScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
    (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);
  });

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

      await act(async () => {
        fireEvent.changeText(emailInput, 'invalid-email');
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(getByText('Please enter a valid email address')).toBeTruthy();
      });
    });

    it('should not show error for valid email', async () => {
      const { getByPlaceholderText, queryByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/auth/forgot-password'),
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(getByText(/Password reset link sent/)).toBeTruthy();
        expect(getByText(/Check your email/)).toBeTruthy();
      });
    });

    it('should show loading indicator during request', async () => {
      global.fetch = jest.fn(() =>
        new Promise(resolve => setTimeout(() =>
          resolve({
            json: () => Promise.resolve({
              success: true,
              message: 'Password reset link sent',
            }),
          } as any)
        , 1000))
      );

      const { getByPlaceholderText, getByTestId, queryByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.press(sendButton);
      });

      // Loading should be shown
      await waitFor(() => {
        expect(getByTestId('activity-indicator')).toBeTruthy();
      });

      // Loading should disappear
      await waitFor(() => {
        expect(queryByTestId('activity-indicator')).toBeNull();
      }, { timeout: 2000 });
    });

    it('should disable send button during request', async () => {
      global.fetch = jest.fn(() =>
        new Promise(resolve => setTimeout(() =>
          resolve({
            json: () => Promise.resolve({ success: true }),
          } as any)
        , 1000))
      );

      const { getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(sendButton.props.disabled).toBe(true);
      });

      await act(async () => {
        jest.advanceTimersByTime(1000);
      });

      await waitFor(() => {
        expect(sendButton.props.disabled).toBe(false);
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
          json: () => Promise.resolve({
            success: false,
            message: 'Email not found',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'notfound@example.com');
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(getByText('Email not found')).toBeTruthy();
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(getByText(/Network error/)).toBeTruthy();
      });
    });

    it('should show rate limit error', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          json: () => Promise.resolve({
            success: false,
            error_code: 'RATE_LIMITED',
            message: 'Too many requests. Please try again later.',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const sendButton = getByTestId('send-reset-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.press(sendButton);
      });

      await waitFor(() => {
        expect(getByText(/Too many requests/)).toBeTruthy();
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
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
          json: () => Promise.resolve({
            success: true,
            message: 'Password reset link sent',
          }),
        } as any)
      );

      const { getByText, getByPlaceholderText, getByTestId } = render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(getByText(/Resend in/)).toBeTruthy();
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
      const { useAuth } = require('../../../../contexts/AuthContext');
      useAuth.mockReturnValue({ isAuthenticated: true });

      render(
        <ForgotPasswordScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('App');
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
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
});
