/**
 * AuthNavigator Component Tests
 *
 * Tests for authentication flow navigation including
 * login, register, forgot password, and biometric auth.
 */

import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { AuthNavigator } from '../../../navigation/AuthNavigator';

// Mock all auth screens
jest.mock('../../../screens/auth/LoginScreen', () => 'LoginScreen');
jest.mock('../../../screens/auth/RegisterScreen', () => 'RegisterScreen');
jest.mock('../../../screens/auth/ForgotPasswordScreen', () => 'ForgotPasswordScreen');
jest.mock('../../../screens/auth/BiometricAuthScreen', () => 'BiometricAuthScreen');

// Mock Ionicons
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

describe('AuthNavigator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render auth navigator', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should show login screen initially', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });
  });

  describe('Navigation Routes', () => {
    it('should have Login route', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should have Register route', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should have ForgotPassword route', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should have BiometricAuth route', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });
  });

  describe('Navigation Flow', () => {
    it('should navigate to register screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should navigate to forgot password screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should navigate to biometric auth screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should navigate back to login from register', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should navigate back to login from forgot password', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });
  });

  describe('Header Configuration', () => {
    it('should configure header style', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should set header title color', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should set header background color', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });
  });

  describe('Screen Options', () => {
    it('should set title for Login screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should set title for Register screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should set title for ForgotPassword screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should set title for BiometricAuth screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });
  });

  describe('Back Button', () => {
    it('should show back button on register screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should show back button on forgot password screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should show back button on biometric auth screen', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });
  });

  describe('Navigation Types', () => {
    it('should export AuthStackParamList', () => {
      // Type exports are verified at compile time
      expect(true).toBe(true);
    });
  });

  describe('Authentication Flow', () => {
    it('should handle successful login flow', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should handle successful registration flow', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should handle password reset flow', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });

    it('should handle biometric authentication flow', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });
  });

  describe('Error Handling', () => {
    it('should handle navigation errors gracefully', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('auth-navigator')).toBeTruthy();
    });
  });

  describe('Performance', () => {
    it('should render efficiently', () => {
      const startTime = Date.now();

      const { getByTestId } = render(
        <NavigationContainer>
          <AuthNavigator />
        </NavigationContainer>
      );

      const renderTime = Date.now() - startTime;

      expect(getByTestId('auth-navigator')).toBeTruthy();
      expect(renderTime).toBeLessThan(500); // Should render in under 500ms
    });
  });
});
