/**
 * Biometric Authentication Tests
 *
 * Tests for biometric authentication functionality including:
 * - Hardware availability detection (hasHardwareAsync)
 * - Enrollment check (isEnrolledAsync)
 * - Authentication success/failure/cancellation
 * - Biometric type detection (Face ID vs Touch ID on iOS, fingerprint on Android)
 * - Error handling for no hardware, not enrolled, user cancellation
 *
 * NOTE: Biometric functionality is implemented in AuthContext.tsx, not a separate service.
 * These tests focus on the biometric-related methods from AuthContext.
 */

// Set environment variable before importing
process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';

// Mock expo-constants before importing AuthContext
jest.mock('expo-constants', () => ({
  expoConfig: {
    extra: {
      eas: {
        projectId: 'test-project-id',
      },
    },
  },
}));

import * as LocalAuthentication from 'expo-local-authentication';
import { renderHook, act } from '@testing-library/react-native';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';

// Mock expo-secure-store
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}));

// Mock expo-local-authentication
jest.mock('expo-local-authentication', () => ({
  hasHardwareAsync: jest.fn(),
  isEnrolledAsync: jest.fn(),
  authenticateAsync: jest.fn(),
  supportedAuthenticationTypesAsync: jest.fn(),
}));

// Mock fetch
global.fetch = jest.fn();

describe('Biometric Authentication (AuthContext)', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Default mock implementations
    (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
    (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: true,
      warning: undefined,
    });
    (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([
      2, // FINGERPRINT
      1, // FACIAL_RECOGNITION
    ]);

    // Mock fetch
    (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    } as Response);
  });

  // ========================================================================
  // Hardware Availability Tests
  // ========================================================================

  describe('Hardware Availability', () => {
    test('should detect biometric hardware is available', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let isAvailable = false;
      await act(async () => {
        isAvailable = await result.current.isBiometricAvailable();
      });

      expect(isAvailable).toBe(true);
      expect(LocalAuthentication.hasHardwareAsync).toHaveBeenCalled();
      expect(LocalAuthentication.isEnrolledAsync).toHaveBeenCalled();
    });

    test('should return false when no hardware available', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let isAvailable = false;
      await act(async () => {
        isAvailable = await result.current.isBiometricAvailable();
      });

      expect(isAvailable).toBe(false);
    });

    test('should return false when not enrolled', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(false);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let isAvailable = false;
      await act(async () => {
        isAvailable = await result.current.isBiometricAvailable();
      });

      expect(isAvailable).toBe(false);
    });

    test('should return false on hardware check error', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockRejectedValue(
        new Error('Hardware check failed')
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let isAvailable = false;
      await act(async () => {
        isAvailable = await result.current.isBiometricAvailable();
      });

      expect(isAvailable).toBe(false);
    });
  });

  // ========================================================================
  // Authentication Tests
  // ========================================================================

  describe('Authentication', () => {
    test('should authenticate successfully with biometric', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: true,
        warning: undefined,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let authResult = { success: false };
      await act(async () => {
        authResult = await result.current.authenticateWithBiometric();
      });

      expect(authResult.success).toBe(true);
      expect(authResult.error).toBeUndefined();
      expect(LocalAuthentication.authenticateAsync).toHaveBeenCalledWith({
        promptMessage: 'Authenticate to access Atom',
        fallbackLabel: 'Use password',
        cancelLabel: 'Cancel',
      });
    });

    test('should handle authentication failure', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Authentication failed',
        warning: undefined,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let authResult = { success: false };
      await act(async () => {
        authResult = await result.current.authenticateWithBiometric();
      });

      expect(authResult.success).toBe(false);
      expect(authResult.error).toBe('Biometric authentication failed');
    });

    test('should handle user cancellation', async () => {
      const error = new Error('User canceled');
      (error as any).code = 'user_cancel';
      (LocalAuthentication.authenticateAsync as jest.Mock).mockRejectedValue(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let authResult = { success: false };
      await act(async () => {
        authResult = await result.current.authenticateWithBiometric();
      });

      expect(authResult.success).toBe(false);
      expect(authResult.error).toBe('Cancelled by user');
    });

    test('should return not available error when hardware missing', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let authResult = { success: false };
      await act(async () => {
        authResult = await result.current.authenticateWithBiometric();
      });

      expect(authResult.success).toBe(false);
      expect(authResult.error).toBe('Biometric not available');
    });

    test('should handle authentication error', async () => {
      (LocalAuthentication.authenticateAsync as jest.Mock).mockRejectedValue(
        new Error('Authentication error')
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let authResult = { success: false };
      await act(async () => {
        authResult = await result.current.authenticateWithBiometric();
      });

      expect(authResult.success).toBe(false);
      expect(authResult.error).toBe('Authentication error');
    });
  });

  // ========================================================================
  // Biometric Registration Tests
  // ========================================================================

  describe('Biometric Registration', () => {
    test('should register biometric successfully', async () => {
      // Mock secure store to have auth token
      const SecureStore = require('expo-secure-store');
      SecureStore.getItemAsync.mockResolvedValue('mock-auth-token');

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      } as Response);

      const AsyncStorage = require('@react-native-async-storage/async-storage');

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let regResult = { success: false };
      await act(async () => {
        regResult = await result.current.registerBiometric('public-key-123');
      });

      expect(regResult.success).toBe(true);
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/auth/mobile/biometric/register',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ public_key: 'public-key-123' }),
        })
      );
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_biometric_enabled', 'true');
    });

    test('should return not authenticated when no token', async () => {
      const SecureStore = require('expo-secure-store');
      SecureStore.getItemAsync.mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let regResult = { success: false };
      await act(async () => {
        regResult = await result.current.registerBiometric('public-key-123');
      });

      expect(regResult.success).toBe(false);
      expect(regResult.error).toBe('Not authenticated');
    });

    test('should handle registration failure', async () => {
      const SecureStore = require('expo-secure-store');
      SecureStore.getItemAsync.mockResolvedValue('mock-auth-token');

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Registration failed' }),
      } as Response);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let regResult = { success: false };
      await act(async () => {
        regResult = await result.current.registerBiometric('public-key-123');
      });

      expect(regResult.success).toBe(false);
      expect(regResult.error).toBe('Registration failed');
    });

    test('should handle registration network error', async () => {
      const SecureStore = require('expo-secure-store');
      SecureStore.getItemAsync.mockResolvedValue('mock-auth-token');

      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let regResult = { success: false };
      await act(async () => {
        regResult = await result.current.registerBiometric('public-key-123');
      });

      expect(regResult.success).toBe(false);
      expect(regResult.error).toBe('Network error');
    });
  });

  // ========================================================================
  // Biometric Type Detection Tests
  // ========================================================================

  describe('Biometric Type Detection', () => {
    test('should get supported authentication types', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([
        1, // FACIAL_RECOGNITION (Face ID)
        2, // FINGERPRINT (Touch ID)
      ]);

      const types = await LocalAuthentication.supportedAuthenticationTypesAsync();

      expect(types).toContain(1); // Face ID supported
      expect(types).toContain(2); // Touch ID supported
    });

    test('should detect only fingerprint on some devices', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([
        2, // FINGERPRINT only
      ]);

      const types = await LocalAuthentication.supportedAuthenticationTypesAsync();

      expect(types).toEqual([2]);
      expect(types).not.toContain(1);
    });
  });

  // ========================================================================
  // Error Handling Tests
  // ========================================================================

  describe('Error Handling', () => {
    test('should handle hasHardwareAsync error', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockRejectedValue(
        new Error('Hardware error')
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let isAvailable = false;
      await act(async () => {
        isAvailable = await result.current.isBiometricAvailable();
      });

      expect(isAvailable).toBe(false);
    });

    test('should handle isEnrolledAsync error', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockRejectedValue(
        new Error('Enrollment check failed')
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      let isAvailable = false;
      await act(async () => {
        isAvailable = await result.current.isBiometricAvailable();
      });

      expect(isAvailable).toBe(false);
    });
  });
});
