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
import { RegisterScreen } from '../../../../screens/auth/RegisterScreen';

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

jest.mock('../../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
  }),
}));

describe('RegisterScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  describe('Rendering', () => {
    it('should render registration form correctly', () => {
      const { getByPlaceholderText, getByText } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      expect(getByPlaceholderText('Full Name')).toBeTruthy();
      expect(getByPlaceholderText('Email')).toBeTruthy();
      expect(getByPlaceholderText('Password')).toBeTruthy();
      expect(getByPlaceholderText('Confirm Password')).toBeTruthy();
      expect(getByText('Sign Up')).toBeTruthy();
      expect(getByText('Already have an account? Sign in')).toBeTruthy();
    });

    it('should display privacy policy link', () => {
      const { getByText } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      expect(getByText('Privacy Policy')).toBeTruthy();
    });

    it('should display terms checkbox', () => {
      const { getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      expect(getByTestId('terms-checkbox')).toBeTruthy();
    });

    it('should display password strength indicator', () => {
      const { getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

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
        expect(getByText('Full name is required')).toBeTruthy();
      });
    });

    it('should show error for invalid email format', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const nameInput = getByPlaceholderText('Full Name');
      const emailInput = getByPlaceholderText('Email');
      const signUpButton = getByTestId('sign-up-button');

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'invalid-email');
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(getByText('Please enter a valid email address')).toBeTruthy();
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, '12345');
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.changeText(confirmInput, 'password456');
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.changeText(confirmInput, 'password123');
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(getByText('You must agree to the terms and conditions')).toBeTruthy();
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'StrongP@ss123');
        fireEvent.changeText(confirmInput, 'StrongP@ss123');
        fireEvent.press(termsCheckbox);
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

      await act(async () => {
        fireEvent.changeText(passwordInput, 'weak');
      });

      await waitFor(() => {
        expect(getByTestId('password-strength-indicator')).toBeTruthy();
        expect(getByText('Weak')).toBeTruthy();
      });
    });

    it('should show medium password strength for moderate password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');

      await act(async () => {
        fireEvent.changeText(passwordInput, 'Moderate123');
      });

      await waitFor(() => {
        expect(getByTestId('password-strength-indicator')).toBeTruthy();
        expect(getByText('Medium')).toBeTruthy();
      });
    });

    it('should show strong password strength for strong password', async () => {
      const { getByPlaceholderText, getByText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');

      await act(async () => {
        fireEvent.changeText(passwordInput, 'Str0ng!P@ssw0rd');
      });

      await waitFor(() => {
        expect(getByTestId('password-strength-indicator')).toBeTruthy();
        expect(getByText('Strong')).toBeTruthy();
      });
    });

    it('should update password strength indicator color', async () => {
      const { getByPlaceholderText, getByTestId } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      const passwordInput = getByPlaceholderText('Password');
      const indicator = getByTestId('password-strength-indicator');

      // Weak - red
      await act(async () => {
        fireEvent.changeText(passwordInput, 'weak');
      });

      await waitFor(() => {
        expect(indicator.props.style).toHaveProperty('color', '#f44336');
      });

      // Strong - green
      await act(async () => {
        fireEvent.changeText(passwordInput, 'Str0ng!P@ssw0rd');
      });

      await waitFor(() => {
        expect(indicator.props.style).toHaveProperty('color', '#4caf50');
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.changeText(confirmInput, 'password123');
        fireEvent.press(termsCheckbox);
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.changeText(confirmInput, 'password123');
        fireEvent.press(termsCheckbox);
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123');
      });
    });

    it('should navigate to app after successful registration', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.changeText(confirmInput, 'password123');
        fireEvent.press(termsCheckbox);
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(mockNavigation.replace).toHaveBeenCalledWith('App');
      });
    });

    it('should show error message on registration failure', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          json: () => Promise.resolve({
            success: false,
            message: 'Email already exists',
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'existing@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.changeText(confirmInput, 'password123');
        fireEvent.press(termsCheckbox);
        fireEvent.press(signUpButton);
      });

      await waitFor(() => {
        expect(getByText('Email already exists')).toBeTruthy();
      });
    });

    it('should show loading indicator during registration', async () => {
      global.fetch = jest.fn(() =>
        new Promise(resolve => setTimeout(() =>
          resolve({
            json: () => Promise.resolve({
              success: true,
              data: { user: { id: 'user-123' }, token: 'test-token' },
            }),
          } as any)
        , 1000))
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

      await act(async () => {
        fireEvent.changeText(nameInput, 'John Doe');
        fireEvent.changeText(emailInput, 'test@example.com');
        fireEvent.changeText(passwordInput, 'password123');
        fireEvent.changeText(confirmInput, 'password123');
        fireEvent.press(termsCheckbox);
        fireEvent.press(signUpButton);
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
  // Navigation Tests
  // ============================================================================

  describe('Navigation', () => {
    it('should navigate to login screen', async () => {
      const { getByText } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      await act(async () => {
        fireEvent.press(getByText('Already have an account? Sign in'));
      });

      expect(mockNavigation.navigate).toHaveBeenCalledWith('Login');
    });

    it('should open privacy policy in browser', async () => {
      const WebBrowser = require('expo-web-browser');
      const { getByText } = render(
        <RegisterScreen navigation={mockNavigation as any} />
      );

      await act(async () => {
        fireEvent.press(getByText('Privacy Policy'));
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
});
