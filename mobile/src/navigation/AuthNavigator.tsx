/**
 * AuthNavigator - Authentication Flow Navigation
 *
 * Manages the authentication flow including:
 * - Login, Register, Forgot Password, Biometric Authentication screens
 * - Conditional rendering based on authentication state
 * - Loading state during token validation
 * - Deep linking support for auth screens
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  NavigationContainer,
  createNavigationContainerRef,
  getStateFromPath,
} from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import {
  ActivityIndicator,
  View,
  StyleSheet,
  StatusBar,
  Linking as RNLinking,
} from 'react-native';

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
  prefixes: ['atom://', 'https://atom.ai/'],
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
 * Deep-link helpers.
 *
 * React Navigation owns prefix stripping during normal linking. These exact
 * boundaries are mirrored here because protected destinations are validated
 * before authentication and replayed through the canonical parser later.
 */
const ATOM_PREFIX = 'atom://';
const HTTPS_PREFIX = 'https://atom.ai/';
const AUTH_ROUTE_NAMES: ReadonlySet<string> = new Set([
  'Login',
  'Register',
  'ForgotPassword',
  'BiometricAuth',
]);

const getPathFromUrl = (url: string): string | undefined => {
  if (url.startsWith(ATOM_PREFIX)) {
    return url.slice(ATOM_PREFIX.length);
  }
  if (url.startsWith(HTTPS_PREFIX)) {
    return url.slice(HTTPS_PREFIX.length);
  }
  return undefined;
};

const getValidatedState = (url: string) => {
  const path = getPathFromUrl(url);
  if (path === undefined || path.length === 0) {
    return undefined;
  }

  try {
    return getStateFromPath<AuthStackParamList>(path, linking.config);
  } catch {
    return undefined;
  }
};

type ParsedNavigationState = NonNullable<ReturnType<typeof getValidatedState>>;

type PendingIntent = {
  state: ParsedNavigationState;
  sequence: number;
};

const isAuthRouteState = (state: ParsedNavigationState): boolean =>
  state.routes.some(route => AUTH_ROUTE_NAMES.has(route.name));

/**
 * AuthNavigator Component
 *
 * Conditionally renders auth flow or main app based on authentication state
 */
export const AuthNavigator: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [isReady, setIsReady] = useState(false);
  const [navigationReady, setNavigationReady] = useState(false);
  const [pendingIntent, setPendingIntent] = useState<PendingIntent | null>(null);

  const navigationRef = useMemo(
    () => createNavigationContainerRef<AuthStackParamList>(),
    []
  );
  const isAuthenticatedRef = useRef(isAuthenticated);
  const pendingIntentRef = useRef<PendingIntent | null>(null);
  const mountedRef = useRef(true);
  const latestSequenceRef = useRef(0);
  const requestSequenceRef = useRef(0);
  const initialUrlRequestedRef = useRef(false);

  isAuthenticatedRef.current = isAuthenticated;

  // Wait for navigation to be ready
  useEffect(() => {
    // The previous implementation wrapped this in a try/catch whose body
    // was only a comment — the catch was provably unreachable (nothing in
    // the try could throw). The finally just marked readiness, so the
    // try/finally is replaced with a direct state set.
    setIsReady(true);
  }, []);

  const acceptUrl = useCallback(
    (url: string, sequence: number): 'forward' | 'handled' | 'ignored' => {
      // A late initial URL must not replace a newer foreground event.
      if (sequence < latestSequenceRef.current) {
        return 'ignored';
      }

      const state = getValidatedState(url);
      if (!state) {
        return 'ignored';
      }

      latestSequenceRef.current = sequence;

      if (isAuthRouteState(state)) {
        // A newer valid URL supersedes an older protected return.
        if (pendingIntentRef.current !== null) {
          pendingIntentRef.current = null;
          setPendingIntent(null);
        }
        return isAuthenticatedRef.current ? 'ignored' : 'forward';
      }

      // Protected destinations are held as intent only. They are never
      // mounted or entered until the authenticated tree is registered.
      const intent: PendingIntent = { state, sequence };
      pendingIntentRef.current = intent;
      setPendingIntent(intent);
      return 'handled';
    },
    []
  );

  const consumePendingIntent = useCallback(() => {
    const intent = pendingIntentRef.current;
    if (!intent || !isAuthenticatedRef.current || !navigationRef.isReady()) {
      return;
    }

    const registered = navigationRef.getRootState().routeNames;
    if (!intent.state.routes.every(route => registered.includes(route.name))) {
      return;
    }

    // Clear before navigating so it can only ever be consumed once.
    pendingIntentRef.current = null;
    setPendingIntent(null);
    navigationRef.resetRoot(intent.state);
  }, [navigationRef]);

  const linkingOptions = useMemo<AuthLinkingOptions>(
    () => ({
      ...linking,
      async getInitialURL() {
        // Native reports the launch URL; process the first report once.
        if (initialUrlRequestedRef.current) {
          return undefined;
        }
        initialUrlRequestedRef.current = true;

        const requestSequence = ++requestSequenceRef.current;
        const initialUrl = Promise.resolve()
          .then(() => RNLinking.getInitialURL())
          .then(url => {
            if (!mountedRef.current || !url) return undefined;
            return acceptUrl(url, requestSequence) === 'forward' ? url : undefined;
          })
          .catch(() => undefined);

        // Preserve React Navigation 6's native 150ms launch-URL fallback.
        // The underlying read may still deliver a validated intent later; it
        // must not hold the login UI hostage or replace a newer valid event.
        let cancelTimer = () => {};
        const fallback = new Promise<undefined>(resolve => {
          const timer = setTimeout(resolve, 150);
          cancelTimer = () => clearTimeout(timer);
        });
        return Promise.race([initialUrl, fallback]).finally(cancelTimer);
      },
      subscribe(listener) {
        let active = true;
        const onReceiveUrl = (event: { url: string }) => {
          if (!active || !mountedRef.current || typeof event.url !== 'string') {
            return;
          }

          const eventSequence = ++requestSequenceRef.current;
          if (acceptUrl(event.url, eventSequence) === 'forward') {
            listener(event.url);
          }
        };

        const subscription = RNLinking.addEventListener('url', onReceiveUrl);
        return () => {
          active = false;
          subscription?.remove();
        };
      },
    }),
    [acceptUrl]
  );

  useEffect(() => {
    if (!isAuthenticated || !navigationReady || pendingIntent === null) {
      return;
    }
    consumePendingIntent();
  }, [consumePendingIntent, isAuthenticated, navigationReady, pendingIntent]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      pendingIntentRef.current = null;
    };
  }, []);

  if (!isReady || isLoading) {
    return <LoadingScreen />;
  }

  return (
    <NavigationContainer
      ref={navigationRef}
      linking={linkingOptions}
      onStateChange={consumePendingIntent}
      onReady={() => {
        setNavigationReady(true);
        consumePendingIntent();
      }}
    >
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
