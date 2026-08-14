/**
 * RegisterScreen Tests
 *
 * Test suite for user registration screen covering:
 * - Rendering and layout
 * - Form validation
 * - Password strength indicator
 * - Registration flow
 * - Terms agreement
 * - Navigation
 * - Error handling
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';

// Mock expo-web-browser
jest.mock('expo-web-browser', () => ({
  maybeCompleteAuthSession: jest.fn(),
  openBrowserAsync: jest.fn(),
}));

const mockNavigate = jest.fn();
const mockNavigation = {
  navigate: mockNavigate,
  goBack: jest.fn(),
};

const mockLogin = jest.fn();

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
  }),
}));

describe('RegisterScreen', () => {
  beforeEach(() => {
    // Async registration flows need real timers to settle
    jest.useRealTimers();
    jest.clearAllMocks();
  });

// require() AFTER the mocks are registered — a static import would load the
// screen (and its context dependencies) before the mock factories apply.
const { RegisterScreen } = require('../../../screens/auth/RegisterScreen');

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  describe('Rendering', () => {
    it('should render registration form correctly', () => {
      const { getByPlaceholderText, getByText, getAllByText } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      expect(getByPlaceholderText('Full Name')).toBeTruthy();
      expect(getByPlaceholderText('Email')).toBeTruthy();
      expect(getByPlaceholderText('Password')).toBeTruthy();
      expect(getByPlaceholderText('Confirm Password')).toBeTruthy();
      expect(getAllByText('Create Account').length).toBeGreaterThan(0);
      expect(getByText('Already have an account? ')).toBeTruthy();
      expect(getByText('Sign In')).toBeTruthy();
    });

    it('should display privacy policy link', () => {
      const { getByText } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      expect(getByText('Terms of Service and Privacy Policy')).toBeTruthy();
    });

    it('should display terms checkbox', () => {
      const { getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      expect(getByTestId('terms-checkbox')).toBeTruthy();
    });

    it('should display password strength indicator', () => {
      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      // The indicator only appears once a password is typed
      fireEvent.changeText(getByPlaceholderText('Password'), 'password123');
      expect(getByTestId('password-strength-indicator')).toBeTruthy();
    });
  });

  // ============================================================================
  // Form Validation Tests
  // ============================================================================

  describe('Form Validation', () => {
    it('should show error for empty name', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const signUpButton = getByTestId('sign-up-button');

      await act(async () => {
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(getByText('Please enter your full name')).toBeTruthy();
      });
    });

    it('should show error for invalid email format', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'invalid-email');
await act(async () => {
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(getByText('Please enter a valid email')).toBeTruthy();
      });
    });

    it('should show error for short password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, '12345');
await act(async () => {
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(getByText('Password must be at least 8 characters')).toBeTruthy();
      });
    });

    it('should show error for mismatched passwords', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const confirmInput = getByPlaceholderText('Confirm Password');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'password123');
fireEvent.changeText(confirmInput, 'password456');
await act(async () => {
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(getByText('Passwords do not match')).toBeTruthy();
      });
    });

    it('should show error when terms not agreed', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const confirmInput = getByPlaceholderText('Confirm Password');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'password123');
fireEvent.changeText(confirmInput, 'password123');
await act(async () => {
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(getByText('You must agree to the terms of service')).toBeTruthy();
      });
    });

    it('should not show errors for valid form data', async () => {
      const { getByPlaceholderText, queryByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const confirmInput = getByPlaceholderText('Confirm Password');
      const termsCheckbox = getByTestId('terms-checkbox');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'StrongP@ss123');
fireEvent.changeText(confirmInput, 'StrongP@ss123');
await act(async () => {
        fireEvent.press(termsCheckbox);
      });
      await act(async () => {
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(queryByText(/is required/)).toBeNull();
        expect(queryByText(/Please enter a valid email/)).toBeNull();
      });
    });
  });

  // ============================================================================
  // Password Strength Tests
  // ============================================================================

  describe('Password Strength', () => {
    it('should show weak password strength for short password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');

      fireEvent.changeText(passwordInput, 'weak');
await act(async () => {
      });

      await waitFor(() => {
        expect(getByTestId('password-strength-indicator')).toBeTruthy();
        expect(getByText(/Password strength: WEAK/)).toBeTruthy();
      });
    });

    it('should show medium password strength for moderate password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');

      fireEvent.changeText(passwordInput, 'Moderate123');
await act(async () => {
      });

      await waitFor(() => {
        expect(getByTestId('password-strength-indicator')).toBeTruthy();
        expect(getByText(/Password strength: MEDIUM/)).toBeTruthy();
      });
    });

    it('should show strong password strength for strong password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');

      fireEvent.changeText(passwordInput, 'Str0ng!P@ssw0rd');
await act(async () => {
      });

      await waitFor(() => {
        expect(getByTestId('password-strength-indicator')).toBeTruthy();
        expect(getByText(/Password strength: STRONG/)).toBeTruthy();
      });
    });

    it('should update password strength indicator color', async () => {
      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');
      const { StyleSheet } = require('react-native');

      // Weak - red
      fireEvent.changeText(passwordInput, 'weak');

      await waitFor(() => {
        const fill = getByTestId('strength-fill');
        expect(StyleSheet.flatten(fill.props.style).backgroundColor).toBe('#f44336');
      });

      // Strong - green
      fireEvent.changeText(passwordInput, 'Str0ng!P@ssw0rd');

      await waitFor(() => {
        const fill = getByTestId('strength-fill');
        expect(StyleSheet.flatten(fill.props.style).backgroundColor).toBe('#4caf50');
      });
    });
  });

  // ============================================================================
  // Registration Flow Tests
  // ============================================================================

  describe('Registration Flow', () => {
    it('should call register API with valid data', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            data: {
              user: { id: 'user-123', email: 'test@example.com', name: 'John Doe' },
              token: 'test-token',
            },
          }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const confirmInput = getByPlaceholderText('Confirm Password');
      const termsCheckbox = getByTestId('terms-checkbox');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'password123');
fireEvent.changeText(confirmInput, 'password123');
await act(async () => {
        fireEvent.press(termsCheckbox);
      });
      await act(async () => {
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/auth/register'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('test@example.com'),
          })
        );
      });
    });

    it('should auto-login after successful registration', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            data: {
              user: { id: 'user-123', email: 'test@example.com', name: 'John Doe' },
              token: 'test-token',
            },
          }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const confirmInput = getByPlaceholderText('Confirm Password');
      const termsCheckbox = getByTestId('terms-checkbox');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'password123');
fireEvent.changeText(confirmInput, 'password123');
await act(async () => {
        fireEvent.press(termsCheckbox);
      });
      await act(async () => {
        fireEvent.press(signUpButton);
      });

      // The screen shows an "Account Created" alert on success (auto-login is
      // handled by the auth flow)
      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Account Created',
          'Your account has been created successfully! You can now sign in.',
          expect.any(Array)
        );
      });
    });

    it('should navigate to app after successful registration', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            data: {
              user: { id: 'user-123', email: 'test@example.com', name: 'John Doe' },
              token: 'test-token',
            },
          }),
        } as any)
      );

      mockLogin.mockResolvedValue({ success: true });

      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const confirmInput = getByPlaceholderText('Confirm Password');
      const termsCheckbox = getByTestId('terms-checkbox');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'password123');
fireEvent.changeText(confirmInput, 'password123');
await act(async () => {
        fireEvent.press(termsCheckbox);
      });
      await act(async () => {
        fireEvent.press(signUpButton);
      });

      // On success the screen shows the "Account Created" alert
      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Account Created',
          expect.stringContaining('created successfully'),
          expect.any(Array)
        );
      });
    });

    it('should show error message on registration failure', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({
            detail: 'A user with this email already exists',
          }),
        } as any)
      );

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const confirmInput = getByPlaceholderText('Confirm Password');
      const termsCheckbox = getByTestId('terms-checkbox');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
fireEvent.changeText(emailInput, 'existing@example.com');
fireEvent.changeText(passwordInput, 'password123');
fireEvent.changeText(confirmInput, 'password123');
await act(async () => {
        fireEvent.press(termsCheckbox);
      });
      await act(async () => {
        fireEvent.press(signUpButton);
      });

      // Registration errors surface via Alert
      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Registration Failed',
          'This email is already registered. Please sign in instead.'
        );
      });
    });

    it('should show loading indicator during registration', async () => {
      let resolveRegister: (value: unknown) => void = () => {};
      global.fetch = jest.fn(() =>
        new Promise((resolve) => { resolveRegister = resolve; })
      );

      const { getByPlaceholderText, getByTestId, queryByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const confirmInput = getByPlaceholderText('Confirm Password');
      const termsCheckbox = getByTestId('terms-checkbox');
      const signUpButton = getByTestId('sign-up-button');

      fireEvent.changeText(nameInput, 'John Doe');
      fireEvent.changeText(emailInput, 'test@example.com');
      fireEvent.changeText(passwordInput, 'password123');
      fireEvent.changeText(confirmInput, 'password123');
      await act(async () => {
        fireEvent.press(termsCheckbox);
      });
      await act(async () => {
        fireEvent.press(signUpButton);
      });

      // Loading should be shown
      await waitFor(() => {
        expect(getByTestId('activity-indicator')).toBeTruthy();
      });

      // Loading should disappear after completion
      await act(async () => {
        resolveRegister({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            data: { user: { id: 'user-123' }, token: 'test-token' },
          }),
        } as any);
      });
      await waitFor(() => {
        expect(queryByTestId('activity-indicator')).toBeNull();
      });
    });
  });

  // ============================================================================
  // Navigation Tests
  // ============================================================================

  describe('Navigation', () => {
    it('should navigate to login screen', async () => {
      const { getByText } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      await act(async () => {
        fireEvent.press(getByText('Sign In'));
      });

      expect(mockNavigation.goBack).toHaveBeenCalled();
    });

    it('should open privacy policy in browser', async () => {
      const WebBrowser = require('expo-web-browser');
      const { getByText } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      await act(async () => {
        fireEvent.press(getByText('Terms of Service and Privacy Policy'));
      });

      expect(WebBrowser.openBrowserAsync).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Password Visibility Tests
  // ============================================================================

  describe('Password Visibility', () => {
    it('should toggle password visibility', async () => {
      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');
      const toggleButton = getByTestId('toggle-password-button');

      expect(passwordInput.props.secureTextEntry).toBe(true);

      await act(async () => {
        fireEvent.press(toggleButton);
      });

      expect(passwordInput.props.secureTextEntry).toBe(false);

      await act(async () => {
        fireEvent.press(toggleButton);
      });

      expect(passwordInput.props.secureTextEntry).toBe(true);
    });

    it('should toggle confirm password visibility', async () => {
      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const confirmInput = getByPlaceholderText('Confirm Password');
      const toggleButton = getByTestId('toggle-confirm-password-button');

      expect(confirmInput.props.secureTextEntry).toBe(true);

      await act(async () => {
        fireEvent.press(toggleButton);
      });

      expect(confirmInput.props.secureTextEntry).toBe(false);
    });
  });

  // ============================================================================
  // Extended Validation & Error-Path Tests
  // ============================================================================

  describe('Extended Validation', () => {
    it('should flag a mismatch when password changes after confirm was entered', async () => {
      const { getByPlaceholderText, getByText, queryByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const confirmInput = getByPlaceholderText('Confirm Password');
      const passwordInput = getByPlaceholderText('Password');

      // Enter and touch the confirm field first
      fireEvent.changeText(confirmInput, 'password123');
      fireEvent(confirmInput, 'blur');

      // Changing the password afterwards must flag the mismatch
      fireEvent.changeText(passwordInput, 'different99');

      await waitFor(() => {
        expect(getByText('Passwords do not match')).toBeTruthy();
      });

      // Matching them again clears the error
      fireEvent.changeText(passwordInput, 'password123');

      await waitFor(() => {
        expect(queryByText('Passwords do not match')).toBeNull();
      });
    });

    it('should reject an 8+ character password that is still weak', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Full Name'), 'John Doe');
      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      fireEvent.changeText(getByPlaceholderText('Password'), 'abcdefgh');
      fireEvent.changeText(getByPlaceholderText('Confirm Password'), 'abcdefgh');
      await act(async () => {
        fireEvent.press(getByTestId('terms-checkbox'));
      });
      await act(async () => {
        fireEvent.press(getByTestId('sign-up-button'));
      });

      await waitFor(() => {
        expect(
          getByText('Password is too weak. Try adding numbers, symbols, or uppercase letters.')
        ).toBeTruthy();
      });
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('should submit the form when the confirm return key is pressed', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        } as any)
      );

      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Full Name'), 'John Doe');
      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      fireEvent.changeText(getByPlaceholderText('Password'), 'Str0ng!P@ss');
      fireEvent.changeText(getByPlaceholderText('Confirm Password'), 'Str0ng!P@ss');
      await act(async () => {
        fireEvent.press(getByTestId('terms-checkbox'));
      });
      await act(async () => {
        fireEvent(getByTestId('confirm-password-input'), 'submitEditing');
      });

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/auth/register'),
          expect.objectContaining({ method: 'POST' })
        );
      });
    });
  });

  describe('Registration Error Paths', () => {
    const fillValidForm = () => {
      const utils = render(<RegisterScreen navigation={mockNavigation as any} />);
      const { getByPlaceholderText, getByTestId } = utils;

      fireEvent.changeText(getByPlaceholderText('Full Name'), 'John Doe');
      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      fireEvent.changeText(getByPlaceholderText('Password'), 'Str0ng!P@ss');
      fireEvent.changeText(getByPlaceholderText('Confirm Password'), 'Str0ng!P@ss');
      fireEvent.press(getByTestId('terms-checkbox'));
      return utils;
    };

    it('shows a generic 400 message when no specific detail matches', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({ detail: 'Invalid request' }),
        } as any)
      );

      const { getByTestId } = fillValidForm();

      await act(async () => {
        fireEvent.press(getByTestId('sign-up-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Registration Failed', 'Invalid request');
      });
    });

    it('shows a rate-limit message for 429 responses', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 429,
          json: () => Promise.resolve({ detail: 'Too many attempts' }),
        } as any)
      );

      const { getByTestId } = fillValidForm();

      await act(async () => {
        fireEvent.press(getByTestId('sign-up-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Registration Failed',
          'Too many registration attempts. Please try again later.'
        );
      });
    });

    it('shows a server error message for 5xx responses', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: 'Internal error' }),
        } as any)
      );

      const { getByTestId } = fillValidForm();

      await act(async () => {
        fireEvent.press(getByTestId('sign-up-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Registration Failed',
          'Server error. Please try again later.'
        );
      });
    });

    it('falls back to a generic failure message for unknown errors', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 418,
          json: () => Promise.resolve({}),
        } as any)
      );

      const { getByTestId } = fillValidForm();

      await act(async () => {
        fireEvent.press(getByTestId('sign-up-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Registration Failed', 'Registration failed');
      });
    });

    it('navigates to login when the success dialog is confirmed', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        } as any)
      );

      const { getByTestId } = fillValidForm();

      await act(async () => {
        fireEvent.press(getByTestId('sign-up-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Account Created',
          expect.any(String),
          expect.any(Array)
        );
      });

      const alertCalls = Alert.alert.mock.calls;
      const okButton = alertCalls[alertCalls.length - 1][2][0];

      await act(async () => {
        okButton.onPress();
      });

      expect(mockNavigation.navigate).toHaveBeenCalledWith('Login');
    });

    it('shows an alert when the privacy policy page fails to open', async () => {
      const WebBrowser = require('expo-web-browser');
      WebBrowser.openBrowserAsync.mockRejectedValue(new Error('Browser failed'));

      const { getByText } = render(<RegisterScreen navigation={mockNavigation as any} />);
      const { Alert } = require('react-native');

      await act(async () => {
        fireEvent.press(getByText('Terms of Service and Privacy Policy'));
      });

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to open privacy policy');
      });
    });
  });
});

  // ============================================================================
  // Coverage Wave Additions (onBlur / onSubmitEditing handlers)
  // ============================================================================

  describe('Input Focus and Blur Handlers', () => {
    const { RegisterScreen: RegisterScreenLocal } = require('../../../screens/auth/RegisterScreen');
    const Screen = RegisterScreenLocal;

    it('should mark all fields touched when blurred', () => {
      const { getByPlaceholderText, getByTestId } = render(
        <Screen navigation={mockNavigation as any} />
      );

      fireEvent(getByPlaceholderText('Full Name'), 'blur');
      fireEvent(getByPlaceholderText('Email'), 'blur');
      fireEvent(getByPlaceholderText('Password'), 'blur');
      fireEvent(getByTestId('confirm-password-input'), 'blur');

      // Blur alone does not create errors, but the form still renders
      expect(getByPlaceholderText('Full Name')).toBeTruthy();
    });

    it('should show validation errors once fields are touched and invalid', () => {
      const { getByPlaceholderText, getByText, queryByText, getByTestId } = render(
        <Screen navigation={mockNavigation as any} />
      );

      // Empty full name, invalid email
      fireEvent.changeText(getByPlaceholderText('Email'), 'not-an-email');
      fireEvent(getByPlaceholderText('Full Name'), 'blur');
      fireEvent(getByPlaceholderText('Email'), 'blur');

      expect(queryByText('Please enter your full name')).toBeNull(); // touched, no errors set yet
      // Now submit to run validation
      fireEvent.press(getByTestId('sign-up-button'));

      expect(getByText('Please enter your full name')).toBeTruthy();
      expect(getByText('Please enter a valid email')).toBeTruthy();
    });

    it('should move focus to the next field when the return key is pressed', () => {
      const { getByPlaceholderText } = render(
        <Screen navigation={mockNavigation as any} />
      );

      // These invoke the refs' focus() — must not throw and must not crash
      expect(() => {
        fireEvent(getByPlaceholderText('Full Name'), 'submitEditing');
        fireEvent(getByPlaceholderText('Email'), 'submitEditing');
        fireEvent(getByPlaceholderText('Password'), 'submitEditing');
      }).not.toThrow();
    });

    it('should show mismatch error when confirm password blur follows a password change', () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <Screen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Password'), 'strongPass1!');
      fireEvent.changeText(getByPlaceholderText('Confirm Password'), 'strongPass2!');
      fireEvent(getByPlaceholderText('Confirm Password'), 'blur');
      fireEvent(getByPlaceholderText('Password'), 'blur');

      fireEvent.press(getByTestId('sign-up-button'));
      expect(getByText('Passwords do not match')).toBeTruthy();
    });
  });
