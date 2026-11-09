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
import { LoginScreen, RegisterScreen, ForgotPasswordScreen, BiometricAuthScreen } from '../screens/auth';
import { AppNavigator } from './AppNavigator';

// Navigation Types
import type {
  AuthLinkingOptions,
  AuthStackParamList,
  CanvasViewerParams,
  MainTabParamList,
} from './types';

// Preserve the public aliases that callers already import from this module.
export type { AuthStackParamList, CanvasViewerParams, MainTabParamList };

const Stack = createNativeStackNavigator<AuthStackParamList>();

const AuthenticatedAppNavigator = () => <AppNavigator embedded />;

// Resolve the native viewer only when its authenticated route is rendered.
// Unrelated auth/tab startup must not initialize a WebView host.
const getCanvasViewerScreen = () => {
  const screens: typeof import('../screens/canvas/CanvasViewerScreen') = require('../screens/canvas/CanvasViewerScreen');
  return screens.CanvasViewerScreen;
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
 *
 * Supported deep link patterns:
 * - Auth: atom://auth/login, atom://auth/register, atom://auth/reset, atom://auth/biometric
 * - Main: atom://workflows, atom://analytics, atom://agents, atom://chat, atom://settings
 * - Resources: atom://agent/{agent_id}, atom://workflow/{workflow_id}, atom://canvas/{canvas_id}
 * - Executions: atom://execution/{execution_id}, atom://execution/{execution_id}/logs
 * - Conversations: atom://chat/{conversation_id}
 *
 * Also supports HTTPS links: https://atom.ai/...
 */
export const linking: AuthLinkingOptions = {
  prefixes: ['atom://', 'https://atom.ai'],
  config: {
    screens: {
      // Auth screens
      Login: {
        path: 'auth/login',
      },
      Register: {
        path: 'auth/register',
      },
      ForgotPassword: {
        path: 'auth/reset',
      },
      BiometricAuth: {
        path: 'auth/biometric',
      },

      // Canvas viewer is registered in the authenticated branch of this stack.
      CanvasViewer: {
        path: 'canvas/:canvasId',
      },

      // Main app screens with nested navigation
      Main: {
        screens: {
          // Workflows tab
          WorkflowsTab: {
            screens: {
              WorkflowsList: {
                path: 'workflows',
              },
              WorkflowDetail: {
                path: 'workflow/:workflowId',
              },
              WorkflowTrigger: {
                path: 'workflow/:workflowId/trigger',
              },
              ExecutionProgress: {
                path: 'execution/:executionId',
              },
              WorkflowLogs: {
                path: 'execution/:executionId/logs',
              },
            },
          },

          // Analytics tab
          AnalyticsTab: {
            path: 'analytics',
          },

          // Agents tab
          AgentsTab: {
            screens: {
              AgentList: {
                path: 'agents',
              },
              AgentChat: {
                path: 'agent/:agentId',
              },
            },
          },

          // Chat tab
          ChatTab: {
            screens: {
              ChatTab: {
                path: 'chat',
              },
              AgentChat: {
                path: 'chat/:conversationId',
              },
            },
          },

          // Settings tab
          SettingsTab: {
            path: 'settings',
          },
        },
      },
    },
  },
};

/**
 * Unauthenticated links must not resolve protected routes such as CanvasViewer.
 * The authenticated tree uses the full linking configuration above.
 */
const unauthenticatedLinking: AuthLinkingOptions = {
  prefixes: linking.prefixes,
  config: {
    screens: {
      Login: {
        path: 'auth/login',
      },
      Register: {
        path: 'auth/register',
      },
      ForgotPassword: {
        path: 'auth/reset',
      },
      BiometricAuth: {
        path: 'auth/biometric',
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
    // The previous implementation wrapped this in a try/catch whose body
    // was only a comment — the catch was provably unreachable (nothing in
    // the try could throw). The finally just marked readiness, so the
    // try/finally is replaced with a direct state set.
    setIsReady(true);
  }, []);

  if (!isReady || isLoading) {
    return <LoadingScreen />;
  }

  return (
    <NavigationContainer linking={isAuthenticated ? linking : unauthenticatedLinking}>
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
              component={AuthenticatedAppNavigator}
              options={{
                headerShown: false,
              }}
            />
            {/* Authenticated resource destination, matching CanvasViewerScreen's
                own navigation.push('CanvasViewer', { canvasId }) contract. */}
            <Stack.Screen
              name="CanvasViewer"
              getComponent={getCanvasViewerScreen}
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
