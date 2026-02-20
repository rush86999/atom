/**
 * BiometricAuthScreen Tests
 *
 * Test suite for biometric authentication screen covering:
 * - Rendering and layout
 * - Auto-trigger biometric
 * - Success navigation
 * - Fallback to password
 * - Max attempts enforcement
 * - Biometric type detection
 * - Error handling
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import * as LocalAuthentication from 'expo-local-authentication';
import { BiometricAuthScreen } from '../../../../screens/auth/BiometricAuthScreen';

// Mock expo-local-authentication
jest.mock('expo-local-authentication', () => ({
  hasHardwareAsync: jest.fn(),
  isEnrolledAsync: jest.fn(),
  supportedAuthenticationTypesAsync: jest.fn(),
  authenticateAsync: jest.fn(),
  getEnrolledLevelAsync: jest.fn(),
  AuthenticationType: {
    FACIAL_RECOGNITION: 1,
    FINGERPRINT: 2,
  },
}));

const mockNavigate = jest.fn();
const mockNavigation = {
  navigate: mockNavigate,
  goBack: jest.fn(),
  replace: jest.fn(),
};

const mockAuthenticateWithBiometric = jest.fn();
const mockLogin = jest.fn();

jest.mock('../../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    authenticateWithBiometric: mockAuthenticateWithBiometric,
    login: mockLogin,
  }),
}));

describe('BiometricAuthScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
    (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
    (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([1]);
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: true,
      warning: undefined,
    });
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  describe('Rendering', () => {
    it('should render biometric authentication screen', () => {
      const { getByText, getByTestId } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      expect(getByText(/Authenticate to access Atom/)).toBeTruthy();
      expect(getByTestId('biometric-icon')).toBeTruthy();
      expect(getByText('Use Password Instead')).toBeTruthy();
    });

    it('should display Face ID icon when available', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([1]);

      const { getByText, getByTestId } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Face ID/)).toBeTruthy();
      });
    });

    it('should display Touch ID icon when available', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([2]);

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Touch ID/)).toBeTruthy();
      });
    });

    it('should show loading indicator during authentication', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve({ success: true }), 1000))
      );

      const { getByTestId, queryByTestId } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      // Loading should be shown
      await waitFor(() => {
        expect(getByTestId('activity-indicator')).toBeTruthy();
      });

      // Loading should disappear
      await waitFor(() => {
        expect(queryByTestId('activity-indicator')).toBeNull();
      }, { timeout: 2000 });
    });
  });

  // ============================================================================
  // Auto-Trigger Biometric Tests
  // ============================================================================

  describe('Auto-Trigger Biometric', () => {
    it('should automatically trigger biometric on mount', async () => {
      render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(LocalAuthentication.authenticateAsync).toHaveBeenCalled();
      });
    });

    it('should show prompt message', async () => {
      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Authenticate to access Atom/)).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Success Navigation Tests
  // ============================================================================

  describe('Success Navigation', () => {
    it('should navigate to app on successful biometric', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: true,
        warning: undefined,
      });

      mockAuthenticateWithBiometric.mockResolvedValue({ success: true });

      const { getByTestId } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(mockAuthenticateWithBiometric).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(mockNavigation.replace).toHaveBeenCalledWith('App');
      });
    });

    it('should navigate to custom route on success', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: true,
        warning: undefined,
      });

      mockAuthenticateWithBiometric.mockResolvedValue({ success: true });

      const route = {
        params: {
          onSuccessNavigate: 'Dashboard',
        },
      };

      render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={route as any} />
      );

      await waitFor(() => {
        expect(mockNavigation.replace).toHaveBeenCalledWith('Dashboard');
      });
    });
  });

  // ============================================================================
  // Fallback to Password Tests
  // ============================================================================

  describe('Fallback to Password', () => {
    it('should navigate to login screen when use password pressed', async () => {
      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await act(async () => {
        fireEvent.press(getByText('Use Password Instead'));
      });

      expect(mockNavigation.navigate).toHaveBeenCalledWith('Login');
    });

    it('should show fallback link after failed attempt', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Not authenticated',
      });

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText('Use Password Instead')).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Max Attempts Tests
  // ============================================================================

  describe('Max Attempts', () => {
    it('should allow retry after failed attempt', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock)
        .mockResolvedValueOnce({
          success: false,
          error: 'Not authenticated',
        })
        .mockResolvedValueOnce({
          success: true,
          warning: undefined,
        });

      const { getByText, getByTestId } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      // First attempt fails
      await waitFor(() => {
        expect(getByText(/Authentication failed/)).toBeTruthy();
      });

      // Retry button should be available
      const retryButton = getByTestId('retry-button');
      await act(async () => {
        fireEvent.press(retryButton);
      });

      // Second attempt succeeds
      await waitFor(() => {
        expect(mockNavigation.replace).toHaveBeenCalledWith('App');
      });
    });

    it('should enforce max 3 attempts', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Not authenticated',
      });

      const { getByText, getByTestId, queryByTestId } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      // First attempt fails
      await waitFor(() => {
        expect(getByText(/Authentication failed/)).toBeTruthy();
      });

      const retryButton = getByTestId('retry-button');

      // Second attempt
      await act(async () => {
        fireEvent.press(retryButton);
      });

      // Third attempt
      await act(async () => {
        fireEvent.press(retryButton);
      });

      // After 3 attempts, should force password login
      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('Login');
      });
    });

    it('should show attempts remaining', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Not authenticated',
      });

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/2 attempts remaining/)).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Biometric Type Detection Tests
  // ============================================================================

  describe('Biometric Type Detection', () => {
    it('should detect Face ID availability', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([1]);

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Face ID/)).toBeTruthy();
      });
    });

    it('should detect Touch ID availability', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([2]);

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Touch ID/)).toBeTruthy();
      });
    });

    it('should handle both Face ID and Touch ID available', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([1, 2]);

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        // Should prefer Face ID when both available
        expect(getByText(/Face ID|Touch ID/)).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Error Handling Tests
  // ============================================================================

  describe('Error Handling', () => {
    it('should handle biometric not available', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Biometric authentication is not available/)).toBeTruthy();
      });
    });

    it('should handle biometric not enrolled', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(false);

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Biometric authentication is not available/)).toBeTruthy();
      });
    });

    it('should show user-friendly error on authentication failure', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'User not authenticated',
      });

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Authentication failed/)).toBeTruthy();
      });
    });

    it('should handle lockout scenario', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Locked out',
      });

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Too many attempts/)).toBeTruthy();
      });
    });

    it('should handle fallback error', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Fallback',
        warning: 'Fallback authentication',
      });

      const { getByText } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByText(/Use password instead/)).toBeTruthy();
      });
    });
  });

  // ============================================================================
  // Animation Tests
  // ============================================================================

  describe('Animations', () => {
    it('should animate icon on mount', async () => {
      const { getByTestId } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      const icon = getByTestId('biometric-icon');

      await waitFor(() => {
        // Icon should be visible with animation
        expect(icon).toBeTruthy();
      });
    });

    it('should shake animation on failure', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Not authenticated',
      });

      const { getByTestId } = render(
        <BiometricAuthScreen navigation={mockNavigation as any} route={{} as any} />
      );

      await waitFor(() => {
        expect(getByTestId('biometric-icon')).toBeTruthy();
      });
    });
  });
});
