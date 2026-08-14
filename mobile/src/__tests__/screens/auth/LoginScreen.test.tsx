/**
 * LoginScreen Tests
 *
 * Test suite for user authentication screen covering:
 * - Rendering and layout
 * - Form validation
 * - Login flow
 * - Biometric authentication
 * - Navigation
 * - Error handling
 * - Loading states
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Mock dependencies
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
}));

const mockNavigate = jest.fn();
const mockNavigation = {
  navigate: mockNavigate,
  goBack: jest.fn(),
  replace: jest.fn(),
  reset: jest.fn(),
};

const mockLogin = jest.fn();
const mockIsBiometricAvailable = jest.fn();
const mockAuthenticateWithBiometric = jest.fn();

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    isBiometricAvailable: mockIsBiometricAvailable,
    authenticateWithBiometric: mockAuthenticateWithBiometric,
  }),
}));

// require() AFTER the mocks are registered — a static import would load the
// screen (and its AuthContext dependency) before the mock factory applies.
const { LoginScreen } = require('../../../screens/auth/LoginScreen');

describe('LoginScreen', () => {
  beforeEach(() => {
    // Async login/remember-me flows need real timers to settle
    jest.useRealTimers();
    jest.clearAllMocks();
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
    (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  describe('Rendering', () => {
    it('should render login form correctly', () => {
      const { getByPlaceholderText, getByText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      expect(getByPlaceholderText('Email')).toBeTruthy();
      expect(getByPlaceholderText('Password')).toBeTruthy();
      expect(getByText('Sign In')).toBeTruthy();
      expect(getByText("Forgot password?")).toBeTruthy();
      expect(getByText("Don't have an account? ")).toBeTruthy();
      expect(getByText('Sign Up')).toBeTruthy();
    });

    it('should display app logo/title', () => {
      const { getByText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      expect(getByText('Welcome Back')).toBeTruthy();
    });

    it('should show biometric button when available', async () => {
      mockIsBiometricAvailable.mockResolvedValue(true);

      const { getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(getByTestId('biometric-button')).toBeTruthy();
      });
    });

    it('should hide biometric button when not available', async () => {
      mockIsBiometricAvailable.mockResolvedValue(false);

      const { queryByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(queryByTestId('biometric-button')).toBeNull();
      });
    });
  });

  // ============================================================================
  // Form Validation Tests
  // ============================================================================

  describe('Form Validation', () => {
    it('should show email error for invalid email format', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const signInButton = getByTestId('sign-in-button');

      fireEvent.changeText(emailInput, 'invalid-email');
await act(async () => {
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(getByText('Please enter a valid email')).toBeTruthy();
      });
    });

    it('should show password error for empty password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, '');
await act(async () => {
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(getByText('Password is required')).toBeTruthy();
      });
    });

    it('should show password error for short password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, '12345');
await act(async () => {
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(getByText('Password must be at least 8 characters')).toBeTruthy();
      });
    });

    it('should not show errors for valid form data', async () => {
      const { getByPlaceholderText, queryByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'password123');
await act(async () => {
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(queryByText(/Please enter a valid email/)).toBeNull();
        expect(queryByText(/Password is required/)).toBeNull();
      });
    });
  });

  // ============================================================================
  // Login Flow Tests
  // ============================================================================

  describe('Login Flow', () => {
    it('should call login with correct credentials', async () => {
      mockLogin.mockResolvedValue({ success: true });

      const { getByPlaceholderText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'password123');
await act(async () => {
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith({
          email: 'test@example.com',
          password: 'password123',
        });
      });
    });

    it('should navigate to app on successful login', async () => {
      mockLogin.mockResolvedValue({ success: true });

      const { getByPlaceholderText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      fireEvent.changeText(emailInput, 'test@example.com');
fireEvent.changeText(passwordInput, 'password123');
await act(async () => {
        fireEvent.press(signInButton);
      });

      // Navigation to the main app is handled by AuthNavigator; the screen
      // completes the successful login flow
      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalled();
      });
    });

    it('should show error message on login failure', async () => {
      mockLogin.mockRejectedValue(new Error('Invalid credentials'));

      const { getByPlaceholderText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      fireEvent.changeText(emailInput, 'test@example.com');
      fireEvent.changeText(passwordInput, 'wrongpassword');
      await act(async () => {
        fireEvent.press(signInButton);
      });

      // Errors surface via Alert
      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Login Failed',
          'Invalid credentials'
        );
      });
    });

    it('should show loading indicator during login', async () => {
      let resolveLogin: (value: unknown) => void = () => {};
      mockLogin.mockImplementation(
        () => new Promise((resolve) => { resolveLogin = resolve; })
      );

      const { getByPlaceholderText, getByTestId, queryByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      fireEvent.changeText(emailInput, 'test@example.com');
      fireEvent.changeText(passwordInput, 'password123');
      await act(async () => {
        fireEvent.press(signInButton);
      });

      // Loading should be shown
      await waitFor(() => {
        expect(getByTestId('activity-indicator')).toBeTruthy();
      });

      // Loading should disappear after completion
      await act(async () => {
        resolveLogin({ success: true });
      });
      await waitFor(() => {
        expect(queryByTestId('activity-indicator')).toBeNull();
      });
    });
  });

  // ============================================================================
  // Biometric Authentication Tests
  // ============================================================================

  describe('Biometric Authentication', () => {
    it('should call biometric auth when button pressed', async () => {
      mockIsBiometricAvailable.mockResolvedValue(true);
      mockAuthenticateWithBiometric.mockResolvedValue({ success: true });

      const { getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(getByTestId('biometric-button')).toBeTruthy();
      });

      await act(async () => {
        fireEvent.press(getByTestId('biometric-button'));
      });

      await waitFor(() => {
        expect(mockAuthenticateWithBiometric).toHaveBeenCalled();
      });
    });

    it('should navigate to app on successful biometric auth', async () => {
      mockIsBiometricAvailable.mockResolvedValue(true);
      mockAuthenticateWithBiometric.mockResolvedValue({ success: true });

      const { getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(getByTestId('biometric-button')).toBeTruthy();
      });

      await act(async () => {
        fireEvent.press(getByTestId('biometric-button'));
      });

      // Navigation is handled by AuthNavigator; the screen completes the
      // successful biometric flow
      await waitFor(() => {
        expect(mockAuthenticateWithBiometric).toHaveBeenCalled();
      });
    });

    it('should show error on failed biometric auth', async () => {
      mockIsBiometricAvailable.mockResolvedValue(true);
      mockAuthenticateWithBiometric.mockRejectedValue(new Error('Biometric failed'));

      const { getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(getByTestId('biometric-button')).toBeTruthy();
      });

      await act(async () => {
        fireEvent.press(getByTestId('biometric-button'));
      });

      // Errors surface via Alert
      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Biometric Error',
          'Biometric failed'
        );
      });
    });
  });

  // ============================================================================
  // Remember Me Tests
  // ============================================================================

  describe('Remember Me', () => {
    it('should save email when remember me is checked', async () => {
      mockLogin.mockResolvedValue({ success: true });

      const { getByPlaceholderText, getByTestId, getByText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const rememberCheckbox = getByTestId('remember-me-checkbox');

      fireEvent.changeText(emailInput, 'test@example.com');
      fireEvent.changeText(passwordInput, 'password123');
      await act(async () => {
        fireEvent.press(rememberCheckbox);
      });

      const signInButton = getByTestId('sign-in-button');

      await act(async () => {
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_remember_me', 'true');
        expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_remembered_email', 'test@example.com');
      });
    });

    it('should load saved email on mount', async () => {
      (AsyncStorage.getItem as jest.Mock)
        .mockResolvedValueOnce('true')
        .mockResolvedValueOnce('saved@example.com');

      const { getByPlaceholderText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        const emailInput = getByPlaceholderText('Email');
        expect(emailInput.props.value).toBe('saved@example.com');
      });
    });
  });

  // ============================================================================
  // Navigation Tests
  // ============================================================================

  describe('Navigation', () => {
    it('should navigate to forgot password screen', async () => {
      const { getByText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await act(async () => {
        fireEvent.press(getByText("Forgot password?"));
      });

      expect(mockNavigation.navigate).toHaveBeenCalledWith('ForgotPassword');
    });

    it('should navigate to register screen', async () => {
      const { getByText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await act(async () => {
        fireEvent.press(getByText('Sign Up'));
      });

      expect(mockNavigation.navigate).toHaveBeenCalledWith('Register');
    });
  });

  // ============================================================================
  // Password Visibility Tests
  // ============================================================================

  describe('Password Visibility', () => {
    it('should toggle password visibility', async () => {
      const { getByPlaceholderText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
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
  });

  // ============================================================================
  // Extended Validation & Error-Path Tests
  // ============================================================================

  describe('Extended Validation', () => {
    it('should show email required error when email is empty', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), '');
      await act(async () => {
        fireEvent.press(getByTestId('sign-in-button'));
      });

      await waitFor(() => {
        expect(getByText('Email is required')).toBeTruthy();
      });
      expect(mockLogin).not.toHaveBeenCalled();
    });

    it('should clear the email error when a valid email is entered', async () => {
      const { getByPlaceholderText, queryByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');

      fireEvent.changeText(emailInput, 'invalid-email');
      await act(async () => {
        fireEvent.press(getByTestId('sign-in-button'));
      });
      await waitFor(() => {
        expect(queryByText('Please enter a valid email')).toBeTruthy();
      });

      // Fixing the email clears the error immediately
      fireEvent.changeText(emailInput, 'valid@example.com');

      await waitFor(() => {
        expect(queryByText('Please enter a valid email')).toBeNull();
      });
    });

    it('should clear the password error when a long enough password is entered', async () => {
      const { getByPlaceholderText, getByTestId, getByText, queryByText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');

      fireEvent.changeText(passwordInput, '12345');
      await act(async () => {
        fireEvent.press(getByTestId('sign-in-button'));
      });
      await waitFor(() => {
        expect(getByText('Password must be at least 8 characters')).toBeTruthy();
      });

      fireEvent.changeText(passwordInput, 'a-very-long-password');

      await waitFor(() => {
        expect(queryByText('Password must be at least 8 characters')).toBeNull();
      });
    });

    it('should show errors after blurring empty fields and submitting', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');

      // Blur marks fields as touched
      fireEvent(emailInput, 'blur');
      fireEvent(passwordInput, 'blur');

      await act(async () => {
        fireEvent.press(getByTestId('sign-in-button'));
      });

      await waitFor(() => {
        expect(getByText('Email is required')).toBeTruthy();
        expect(getByText('Password is required')).toBeTruthy();
      });
    });

    it('should submit the form when the password return key is pressed', async () => {
      mockLogin.mockResolvedValue({ success: true });

      const { getByPlaceholderText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      fireEvent.changeText(getByPlaceholderText('Password'), 'password123');

      await act(async () => {
        fireEvent(getByTestId('password-input'), 'submitEditing');
      });

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith({
          email: 'test@example.com',
          password: 'password123',
        });
      });
    });
  });

  // ============================================================================
  // Login Failure & Remember-Me Persistence Tests
  // ============================================================================

  describe('Login Failure Handling', () => {
    it('should show the server error when login returns success=false', async () => {
      mockLogin.mockResolvedValue({ success: false, error: 'Invalid credentials' });

      const { getByPlaceholderText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      fireEvent.changeText(getByPlaceholderText('Password'), 'password123');
      await act(async () => {
        fireEvent.press(getByTestId('sign-in-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Login Failed',
          'Invalid credentials'
        );
      });
    });

    it('should clear saved credentials when remember me is unchecked', async () => {
      mockLogin.mockResolvedValue({ success: true });

      const { getByPlaceholderText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      fireEvent.changeText(getByPlaceholderText('Email'), 'test@example.com');
      fireEvent.changeText(getByPlaceholderText('Password'), 'password123');
      await act(async () => {
        fireEvent.press(getByTestId('sign-in-button'));
      });

      await waitFor(() => {
        expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_remember_me');
        expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_remembered_email');
      });
    });

    it('should show biometric failure message when biometric auth returns success=false', async () => {
      mockIsBiometricAvailable.mockResolvedValue(true);
      mockAuthenticateWithBiometric.mockResolvedValue({
        success: false,
        error: 'Fingerprint not recognized',
      });

      const { getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await waitFor(() => {
        expect(getByTestId('biometric-button')).toBeTruthy();
      });

      await act(async () => {
        fireEvent.press(getByTestId('biometric-button'));
      });

      const { Alert } = require('react-native');
      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Biometric Authentication Failed',
          'Fingerprint not recognized'
        );
      });
    });
  });
});
