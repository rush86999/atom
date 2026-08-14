/**
 * navigationMocks Unit Tests
 *
 * Exercises every screen-mock factory: createMockScreen, mockAllScreens,
 * createMockScreenWithContent, createMockScreenWithNavigation,
 * createMockAppNavigator, createMockAuthContext, mockIonicons, and the
 * SCREEN_TEST_IDS constant.
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import {
  createMockScreen,
  mockAllScreens,
  createMockScreenWithContent,
  createMockScreenWithNavigation,
  createMockAppNavigator,
  createMockAuthContext,
  mockIonicons,
  SCREEN_TEST_IDS,
} from '../navigationMocks';

describe('createMockScreen', () => {
  it('renders the screen name', () => {
    const MockScreen = createMockScreen('Login', 'login-screen');
    const { getByTestId, queryByTestId } = render(<MockScreen route={{}} navigation={{}} />);

    expect(getByTestId('login-screen')).toBeTruthy();
    expect(getByTestId('login-screen-name').props.children).toBe('Login');
    expect(queryByTestId('login-screen-params')).toBeNull();
  });

  it('renders serialized params when route params exist', () => {
    const MockScreen = createMockScreen('Login', 'login-screen');
    const { getByTestId } = render(
      <MockScreen route={{ params: { redirect: 'workflows' } }} navigation={{}} />
    );
    expect(getByTestId('login-screen-params').props.children).toBe(
      JSON.stringify({ redirect: 'workflows' })
    );
  });
});

describe('mockAllScreens', () => {
  beforeEach(() => {
    mockAllScreens();
  });

  it('registers functional mocks for every screen module', async () => {
    const { LoginScreen } = require('../../../screens/auth/LoginScreen');
    const { RegisterScreen } = require('../../../screens/auth/RegisterScreen');
    const { ForgotPasswordScreen } = require('../../../screens/auth/ForgotPasswordScreen');
    const { BiometricAuthScreen } = require('../../../screens/auth/BiometricAuthScreen');
    const { WorkflowsListScreen } = require('../../../screens/workflows/WorkflowsListScreen');
    const { WorkflowDetailScreen } = require('../../../screens/workflows/WorkflowDetailScreen');
    const { WorkflowTriggerScreen } = require('../../../screens/workflows/WorkflowTriggerScreen');
    const { ExecutionProgressScreen } = require('../../../screens/workflows/ExecutionProgressScreen');
    const { WorkflowLogsScreen } = require('../../../screens/workflows/WorkflowLogsScreen');
    const { AnalyticsDashboardScreen } = require('../../../screens/analytics/AnalyticsDashboardScreen');
    const { AgentListScreen } = require('../../../screens/agent/AgentListScreen');
    const { AgentChatScreen } = require('../../../screens/agent/AgentChatScreen');
    const { ChatTabScreen } = require('../../../screens/chat');
    const { SettingsScreen } = require('../../../screens/settings/SettingsScreen');

    const { getByTestId } = render(
      <>
        <LoginScreen route={{}} navigation={{}} />
        <RegisterScreen route={{}} navigation={{}} />
        <ForgotPasswordScreen route={{}} navigation={{}} />
        <BiometricAuthScreen route={{}} navigation={{}} />
        <WorkflowsListScreen route={{}} navigation={{}} />
        <WorkflowDetailScreen route={{}} navigation={{}} />
        <WorkflowTriggerScreen route={{}} navigation={{}} />
        <ExecutionProgressScreen route={{}} navigation={{}} />
        <WorkflowLogsScreen route={{}} navigation={{}} />
        <AnalyticsDashboardScreen route={{}} navigation={{}} />
        <AgentListScreen route={{}} navigation={{}} />
        <AgentChatScreen route={{}} navigation={{}} />
        <ChatTabScreen route={{}} navigation={{}} />
        <SettingsScreen route={{}} navigation={{}} />
      </>
    );

    expect(getByTestId('login-screen')).toBeTruthy();
    expect(getByTestId('register-screen')).toBeTruthy();
    expect(getByTestId('forgot-password-screen')).toBeTruthy();
    expect(getByTestId('biometric-auth-screen')).toBeTruthy();
    expect(getByTestId('workflows-list-screen')).toBeTruthy();
    expect(getByTestId('workflow-detail-screen')).toBeTruthy();
    expect(getByTestId('workflow-trigger-screen')).toBeTruthy();
    expect(getByTestId('execution-progress-screen')).toBeTruthy();
    expect(getByTestId('workflow-logs-screen')).toBeTruthy();
    expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
    expect(getByTestId('agent-list-screen')).toBeTruthy();
    expect(getByTestId('agent-chat-screen')).toBeTruthy();
    expect(getByTestId('chat-tab-screen')).toBeTruthy();
    expect(getByTestId('settings-screen')).toBeTruthy();
  });

  it('renders navigation buttons and navigates on press', async () => {
    const { LoginScreen } = require('../../../screens/auth/LoginScreen');
    const navigate = jest.fn();
    const { getByTestId } = render(<LoginScreen route={{}} navigation={{ navigate }} />);

    fireEvent.press(getByTestId('login-screen-nav-Register'));
    expect(navigate).toHaveBeenCalledWith('Register');
  });

  it('handles single-string navigateTo destinations', () => {
    const { RegisterScreen } = require('../../../screens/auth/RegisterScreen');
    const navigate = jest.fn();
    const { getByTestId } = render(<RegisterScreen route={{}} navigation={{ navigate }} />);
    fireEvent.press(getByTestId('register-screen-nav-Login'));
    expect(navigate).toHaveBeenCalledWith('Login');
  });

  it('captures root navigation state via the global hook', async () => {
    const { LoginScreen } = require('../../../screens/auth/LoginScreen');
    const capture = jest.fn();
    (global as any).__atomNavStateCapture = capture;

    const ownState = {
      type: 'stack',
      index: 0,
      routes: [{ key: 'own-1', name: 'Login' }],
    };
    const rootState = {
      type: 'tab',
      index: 0,
      routes: [{ key: 'root-1', name: 'Auth' }],
    };
    const addListener = jest.fn(() => jest.fn());

    try {
      render(
        <LoginScreen
          route={{}}
          navigation={{
            // navigation is a SCREEN inside a tab root: getParent climbs
            // to the root navigator (which owns the tab state)
            getParent: () => ({
              getState: () => rootState,
              addListener,
            }),
            getState: () => ownState,
            addListener,
          }}
        />
      );

      await waitFor(() => {
        expect(capture).toHaveBeenCalled();
      });
      // tab root state gets the focused route's nested state merged in
      const merged = capture.mock.calls[0][0];
      expect(merged.type).toBe('tab');
      expect(merged.routes[0].state).toBe(ownState);
    } finally {
      delete (global as any).__atomNavStateCapture;
    }
  });

  it('captures root navigation state for stack roots', async () => {
    const { LoginScreen } = require('../../../screens/auth/LoginScreen');
    const capture = jest.fn();
    (global as any).__atomNavStateCapture = capture;

    const rootState = {
      type: 'stack',
      index: 0,
      routes: [{ key: 'root-1', name: 'Login' }],
    };

    try {
      render(
        <LoginScreen
          route={{}}
          navigation={{
            getParent: () => null,
            getState: () => rootState,
            addListener: jest.fn(() => jest.fn()),
          }}
        />
      );

      await waitFor(() => {
        expect(capture).toHaveBeenCalled();
      });
      expect(capture.mock.calls[0][1]).toBe('Login');
    } finally {
      delete (global as any).__atomNavStateCapture;
    }
  });
});

describe('createMockScreenWithContent', () => {
  it('renders custom content and params', () => {
    const { Text } = require('react-native');
    const MockScreen = createMockScreenWithContent(
      'workflow-detail-screen',
      React.createElement(Text, null, 'Custom Content')
    );
    const { getByText, getByTestId } = render(
      <MockScreen route={{ params: { id: 'wf-1' } }} navigation={{}} />
    );

    expect(getByText('Custom Content')).toBeTruthy();
    expect(getByTestId('workflow-detail-screen-params').props.children).toBe(
      JSON.stringify({ id: 'wf-1' })
    );
  });

  it('omits params block when route has none', () => {
    const { Text } = require('react-native');
    const MockScreen = createMockScreenWithContent(
      's',
      React.createElement(Text, null, 'Static')
    );
    const { queryByTestId, getByText } = render(<MockScreen route={{}} navigation={{}} />);
    expect(queryByTestId('s-params')).toBeNull();
    expect(getByText('Static')).toBeTruthy();
  });
});

describe('createMockScreenWithNavigation', () => {
  it('invokes the onNavigate callback with navigation', async () => {
    const onNavigate = jest.fn();
    const MockScreen = createMockScreenWithNavigation('login-screen', 'Login', onNavigate);
    const navigation = { navigate: jest.fn() };
    render(<MockScreen route={{}} navigation={navigation} />);

    await waitFor(() => {
      expect(onNavigate).toHaveBeenCalledWith(navigation);
    });
  });

  it('works without an onNavigate callback', () => {
    const MockScreen = createMockScreenWithNavigation('login-screen', 'Login');
    const { getByTestId } = render(<MockScreen route={{}} navigation={{}} />);
    expect(getByTestId('login-screen-name').props.children).toBe('Login');
  });
});

describe('createMockAppNavigator', () => {
  it('renders the app-navigator testID', () => {
    const MockAppNavigator = createMockAppNavigator();
    const { getByTestId } = render(<MockAppNavigator />);
    expect(getByTestId('app-navigator')).toBeTruthy();
  });
});

describe('createMockAuthContext', () => {
  it('creates an authenticated context', () => {
    const ctx = createMockAuthContext(true, false);
    expect(ctx.isAuthenticated).toBe(true);
    expect(ctx.isLoading).toBe(false);
    expect(ctx.user.id).toBe('test-user-123');
    expect(ctx.token).toBe('test-token-abc123');
    expect(typeof ctx.login).toBe('function');
    expect(typeof ctx.logout).toBe('function');
    expect(typeof ctx.register).toBe('function');
    expect(typeof ctx.refreshToken).toBe('function');
  });

  it('creates an unauthenticated context with defaults', () => {
    const ctx = createMockAuthContext();
    expect(ctx.isAuthenticated).toBe(false);
    expect(ctx.isLoading).toBe(false);
    expect(ctx.user).toBeNull();
    expect(ctx.token).toBeNull();
  });

  it('creates a loading context', () => {
    const ctx = createMockAuthContext(false, true);
    expect(ctx.isLoading).toBe(true);
  });
});

describe('mockIonicons', () => {
  it('registers a string mock for @expo/vector-icons', () => {
    mockIonicons();
    const { Ionicons } = require('@expo/vector-icons');
    expect(Ionicons).toBe('Ionicons');
  });
});

describe('SCREEN_TEST_IDS', () => {
  it('exposes testIDs matching the mock screen factories', () => {
    expect(SCREEN_TEST_IDS.WORKFLOWS_LIST).toBe('workflows-list-screen');
    expect(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD).toBe('analytics-dashboard-screen');
    expect(SCREEN_TEST_IDS.AGENT_LIST).toBe('agent-list-screen');
    expect(SCREEN_TEST_IDS.CHAT_TAB).toBe('chat-tab-screen');
    expect(SCREEN_TEST_IDS.SETTINGS).toBe('settings-screen');
    expect(SCREEN_TEST_IDS.WORKFLOW_DETAIL).toBe('workflow-detail-screen');
    expect(SCREEN_TEST_IDS.WORKFLOW_TRIGGER).toBe('workflow-trigger-screen');
    expect(SCREEN_TEST_IDS.EXECUTION_PROGRESS).toBe('execution-progress-screen');
    expect(SCREEN_TEST_IDS.WORKFLOW_LOGS).toBe('workflow-logs-screen');
    expect(SCREEN_TEST_IDS.AGENT_CHAT).toBe('agent-chat-screen');
  });
});
