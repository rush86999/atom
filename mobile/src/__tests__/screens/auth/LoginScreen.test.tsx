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
import { LoginScreen } from '../../../../screens/auth/LoginScreen';

// Mock dependencies
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
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

jest.mock('../../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    isBiometricAvailable: mockIsBiometricAvailable,
    authenticateWithBiometric: mockAuthenticateWithBiometric,
  }),
}));

describe('LoginScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
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
      expect(getByText("Don't have an account? Sign up")).toBeTruthy();
    });

    it('should display app logo/title', () => {
      const { getByText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      expect(getByText('Atom')).toBeTruthy();
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'invalid-email');
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(getByText('Please enter a valid email address')).toBeTruthy();
      });
    });

    it('should show password error for empty password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, '');
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, '12345');
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(getByText('Password must be at least 6 characters')).toBeTruthy();
      });
    });

    it('should not show errors for valid form data', async () => {
      const { getByPlaceholderText, queryByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123');
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

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(mockNavigation.replace).toHaveBeenCalledWith('App');
      });
    });

    it('should show error message on login failure', async () => {
      mockLogin.mockRejectedValue(new Error('Invalid credentials'));

      const { getByPlaceholderText, getByText, getByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'wrongpassword');
        fireEvent.press(signInButton);
      });

      await waitFor(() => {
        expect(getByText('Invalid credentials')).toBeTruthy();
      });
    });

    it('should show loading indicator during login', async () => {
      mockLogin.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ success: true }), 1000)));

      const { getByPlaceholderText, getByTestId, queryByTestId } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      const emailInput = getByPlaceholderText('Email');
      const passwordInput = getByPlaceholderText('Password');
      const signInButton = getByTestId('sign-in-button');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.press(signInButton);
      });

      // Loading should be shown
      await waitFor(() => {
        expect(getByTestId('activity-indicator')).toBeTruthy();
      });

      // Loading should disappear after completion
      await waitFor(() => {
        expect(queryByTestId('activity-indicator')).toBeNull();
      }, { timeout: 2000 });
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

      await act(async () => {
        fireEvent.press(getByTestId('biometric-button'));
      });

      await waitFor(() => {
        expect(mockNavigation.replace).toHaveBeenCalledWith('App');
      });
    });

    it('should show error on failed biometric auth', async () => {
      mockIsBiometricAvailable.mockResolvedValue(true);
      mockAuthenticateWithBiometric.mockRejectedValue(new Error('Biometric failed'));

      const { getByTestId, getByText } = render(
        <LoginScreen navigation={mockNavigation as any} />
      );

      await act(async () => {
        fireEvent.press(getByTestId('biometric-button'));
      });

      await waitFor(() => {
        expect(getByText('Biometric authentication failed')).toBeTruthy();
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
      const rememberCheckbox = getByTestId('remember-me-checkbox');

      await act(async () => {
        fireEvent.changeText(emailInput, 'test@example.com');
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
        fireEvent.press(getByText("Don't have an account? Sign up"));
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
});
