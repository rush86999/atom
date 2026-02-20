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

const Stack = createNativeStackNavigator();

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
const linking = {
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

      // Direct resource deep links (convenience shortcuts)
      Agent: 'agent/:agentId',
      Workflow: 'workflow/:workflowId',
      Canvas: 'canvas/:canvasId',
      Execution: 'execution/:executionId',
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
