/**
 * AuthNavigator - Authentication Flow Navigation
 *
 * Manages the authentication flow including:
 * - Login, Register, Forgot Password, Biometric Authentication screens
 * - Conditional rendering based on authentication state
 * - Loading state during token validation
 * - Deep linking support for auth screens
 */

import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ActivityIndicator, View, StyleSheet, StatusBar } from 'react-native';
import * as Linking from 'expo-linking';

// Context
import { useAuth } from '../contexts/AuthContext';

// Screen Imports
import { LoginScreen, RegisterScreen, ForgotPasswordScreen } from '../screens/auth';
import { AppNavigator } from './AppNavigator';

const Stack = createNativeStackNavigator();

// Placeholder screens until implemented in subsequent tasks
const BiometricAuthScreen = () => null;

/**
 * Navigation Types
 */
export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
  BiometricAuth: { onSuccessNavigate?: string };
  Main: undefined;
};

export type MainTabParamList = {
  WorkflowsTab: undefined;
  AnalyticsTab: undefined;
  AgentsTab: undefined;
  ChatTab: undefined;
  SettingsTab: undefined;
};

/**
 * Loading Screen
 */
const LoadingScreen: React.FC = () => (
  <View style={styles.loadingContainer}>
    <StatusBar barStyle="default" />
    <ActivityIndicator size="large" color="#2196F3" />
  </View>
);

/**
 * Linking configuration for deep links
 */
const linking = {
  prefixes: ['atom://'],
  config: {
    screens: {
      Login: 'auth/login',
      Register: 'auth/register',
      ForgotPassword: 'auth/reset',
      BiometricAuth: 'auth/biometric',
      Main: {
        screens: {
          WorkflowsTab: 'workflows',
          AnalyticsTab: 'analytics',
          AgentsTab: 'agents',
          ChatTab: 'chat',
          SettingsTab: 'settings',
        },
      },
    },
  },
};

/**
 * AuthNavigator Component
 *
 * Conditionally renders auth flow or main app based on authentication state
 */
export const AuthNavigator: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [isReady, setIsReady] = useState(false);

  // Wait for navigation to be ready
  useEffect(() => {
    const prepare = async () => {
      try {
        // Pre-load fonts or perform other setup here if needed
      } catch (e) {
        console.warn('Error preparing app:', e);
      } finally {
        setIsReady(true);
      }
    };

    prepare();
  }, []);

  if (!isReady || isLoading) {
    return <LoadingScreen />;
  }

  return (
    <NavigationContainer linking={linking}>
      <Stack.Navigator
        initialRouteName={isAuthenticated ? 'Main' : 'Login'}
        screenOptions={{
          headerStyle: {
            backgroundColor: '#2196F3',
          },
          headerTintColor: '#fff',
          headerTitleStyle: {
            fontWeight: 'bold',
          },
          animation: 'slide_from_right',
          animationDuration: 250,
        }}
      >
        {!isAuthenticated ? (
          <>
            {/* Auth Flow Screens */}
            <Stack.Screen
              name="Login"
              component={LoginScreen}
              options={{
                title: 'Sign In',
                headerShown: false,
              }}
            />
            <Stack.Screen
              name="Register"
              component={RegisterScreen}
              options={{
                title: 'Create Account',
                headerBackTitle: 'Back',
              }}
            />
            <Stack.Screen
              name="ForgotPassword"
              component={ForgotPasswordScreen}
              options={{
                title: 'Reset Password',
                presentation: 'modal',
              }}
            />
            <Stack.Screen
              name="BiometricAuth"
              component={BiometricAuthScreen}
              options={{
                title: 'Biometric Authentication',
                headerShown: false,
                presentation: 'fullScreenModal',
              }}
            />
          </>
        ) : (
          <>
            {/* Main App */}
            <Stack.Screen
              name="Main"
              component={AppNavigator}
              options={{
                headerShown: false,
              }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
  },
});

export default AuthNavigator;
