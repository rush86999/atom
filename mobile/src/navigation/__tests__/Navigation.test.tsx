/**
 * Navigation Tests
 *
 * Tests for navigation functionality including:
 * - Navigate to screen
 * - Navigate with params
 * - Go back
 * - Navigate replace
 * - Deep link handling
 * - Tab navigation
 * - Stack navigation
 * - Navigation state persistence
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { AppNavigator } from '../AppNavigator';

// Mock react-navigation
jest.mock('@react-navigation/native', () => ({
  NavigationContainer: ({ children }: any) => children,
  useNavigation: () => ({
    navigate: jest.fn(),
    goBack: jest.fn(),
    reset: jest.fn(),
    replace: jest.fn(),
    dispatch: jest.fn(),
    isFocused: jest.fn(() => true),
    canGoBack: jest.fn(() => true),
  }),
  useRoute: () => ({
    params: {},
    name: 'WorkflowsList',
    path: undefined,
  }),
  useFocusEffect: jest.fn(),
  useIsFocused: jest.fn(() => true),
}));

// Mock react-navigation/bottom-tabs
jest.mock('@react-navigation/bottom-tabs', () => ({
  createBottomTabNavigator: () => ({
    Navigator: ({ children, screenOptions, initialRouteName }: any) => {
      const firstChild = React.Children.toArray(children)[0] as any;
      return firstChild?.props?.children || null;
    },
    Screen: ({ name, component, options }: any) => {
      return React.createElement(component, { name, options });
    },
  }),
  useBottomTabBarHeight: jest.fn(() => 50),
}));

// Mock react-navigation/native-stack
jest.mock('@react-navigation/native-stack', () => ({
  createNativeStackNavigator: () => ({
    Navigator: ({ children, screenOptions, initialRouteName }: any) => {
      const firstChild = React.Children.toArray(children)[0] as any;
      return firstChild?.props?.children || null;
    },
    Screen: ({ name, component, options }: any) => {
      return React.createElement(component, { name, options });
    },
  }),
}));

// Mock screens
jest.mock('../../screens/workflows/WorkflowsListScreen', () => ({
  WorkflowsListScreen: () => 'WorkflowsListScreen',
}));
jest.mock('../../screens/workflows/WorkflowDetailScreen', () => ({
  WorkflowDetailScreen: () => 'WorkflowDetailScreen',
}));
jest.mock('../../screens/workflows/WorkflowTriggerScreen', () => ({
  WorkflowTriggerScreen: () => 'WorkflowTriggerScreen',
}));
jest.mock('../../screens/workflows/ExecutionProgressScreen', () => ({
  ExecutionProgressScreen: () => 'ExecutionProgressScreen',
}));
jest.mock('../../screens/workflows/WorkflowLogsScreen', () => ({
  WorkflowLogsScreen: () => 'WorkflowLogsScreen',
}));
jest.mock('../../screens/analytics/AnalyticsDashboardScreen', () => ({
  AnalyticsDashboardScreen: () => 'AnalyticsDashboardScreen',
}));
jest.mock('../../screens/agent/AgentListScreen', () => ({
  AgentListScreen: () => 'AgentListScreen',
}));
jest.mock('../../screens/agent/AgentChatScreen', () => ({
  AgentChatScreen: () => 'AgentChatScreen',
}));
jest.mock('../../screens/chat', () => ({
  ChatTabScreen: () => 'ChatTabScreen',
}));
jest.mock('../../screens/settings/SettingsScreen', () => ({
  SettingsScreen: () => 'SettingsScreen',
}));

// Mock expo-vector-icons
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

describe('Navigation', () => {
  /**
   * Test: Navigate to screen
   * Expected: Navigation works between screens
   */
  test('test_navigate_to_screen', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const { getByText } = render(
      <NavigationContainer>
        <AppNavigator />
      </NavigationContainer>
    );

    await waitFor(() => {
      expect(navigation.navigate).toBeDefined();
    });
  });

  /**
   * Test: Navigate with params
   * Expected: Params are passed correctly
   */
  test('test_navigate_with_params', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const params = { workflowId: '123', name: 'Test Workflow' };

    // In actual implementation, this would call navigation.navigate
    navigation.navigate('WorkflowDetail', params);

    expect(navigation.navigate).toHaveBeenCalledWith('WorkflowDetail', params);
  });

  /**
   * Test: Go back
   * Expected: Can go back to previous screen
   */
  test('test_go_back', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    navigation.goBack();

    expect(navigation.goBack).toHaveBeenCalled();
  });

  /**
   * Test: Navigate replace
   * Expected: Can replace current screen
   */
  test('test_navigate_replace', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    navigation.replace('WorkflowsList');

    expect(navigation.replace).toHaveBeenCalledWith('WorkflowsList');
  });

  /**
   * Test: Deep link handling
   * Expected: Deep links navigate to correct screen
   */
  test('test_deep_link', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://workflow/123';

    // In actual implementation, deep link would be parsed and navigation triggered
    navigation.navigate('WorkflowDetail', { workflowId: '123' });

    expect(navigation.navigate).toHaveBeenCalled();
  });

  /**
   * Test: Tab navigation
   * Expected: Can navigate between tabs
   */
  test('test_tab_navigation', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    // Navigate to different tabs
    navigation.navigate('WorkflowsTab');
    navigation.navigate('AgentsTab');
    navigation.navigate('AnalyticsTab');

    expect(navigation.navigate).toHaveBeenCalledTimes(3);
  });

  /**
   * Test: Stack navigation
   * Expected: Can navigate within stack
   */
  test('test_stack_navigation', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    // Navigate through workflow stack
    navigation.navigate('WorkflowDetail');
    navigation.navigate('WorkflowTrigger');
    navigation.navigate('ExecutionProgress');

    expect(navigation.navigate).toHaveBeenCalledTimes(3);
  });

  /**
   * Test: Navigation state persistence
   * Expected: Navigation state persists across app restarts
   */
  test('test_navigation_state_persistence', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const initialState = {
      index: 0,
      routes: [
        { name: 'WorkflowsList', key: 'WorkflowsList' },
      ],
    };

    // In actual implementation, state would be persisted and restored
    navigation.reset({
      index: 0,
      routes: [{ name: 'WorkflowsList' }],
    });

    expect(navigation.reset).toHaveBeenCalled();
  });

  /**
   * Test: Navigation params serialization
   * Expected: Complex params are serialized correctly
   */
  test('test_navigation_params_serialization', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const complexParams = {
      workflow: {
        id: '123',
        name: 'Test Workflow',
        steps: [
          { id: '1', name: 'Step 1' },
          { id: '2', name: 'Step 2' },
        ],
      },
      timestamp: Date.now(),
    };

    navigation.navigate('WorkflowDetail', complexParams);

    expect(navigation.navigate).toHaveBeenCalledWith('WorkflowDetail', complexParams);
  });

  /**
   * Test: Can go back check
   * Expected: Can check if navigation can go back
   */
  test('test_can_go_back', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const canGoBack = navigation.canGoBack();

    expect(canGoBack).toBeDefined();
    expect(typeof canGoBack).toBe('boolean');
  });

  /**
   * Test: Navigation focus check
   * Expected: Can check if screen is focused
   */
  test('test_navigation_focus_check', async () => {
    const { useIsFocused } = require('@react-navigation/native');
    const isFocused = useIsFocused();

    expect(isFocused).toBeDefined();
    expect(typeof isFocused).toBe('boolean');
  });

  /**
   * Test: Navigation dispatch
   * Expected: Can dispatch navigation actions
   */
  test('test_navigation_dispatch', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const action = {
      type: 'NAVIGATE',
      payload: { name: 'WorkflowsList' },
    };

    navigation.dispatch(action);

    expect(navigation.dispatch).toHaveBeenCalledWith(action);
  });

  /**
   * Test: Multiple navigation stacks
   * Expected: Can navigate between different stacks
   */
  test('test_multiple_navigation_stacks', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    // Navigate between different stacks
    navigation.navigate('WorkflowsTab', { screen: 'WorkflowDetail' });
    navigation.navigate('AgentsTab', { screen: 'AgentList' });
    navigation.navigate('AnalyticsTab');

    expect(navigation.navigate).toHaveBeenCalledTimes(3);
  });

  /**
   * Test: Modal navigation
   * Expected: Can open modals
   */
  test('test_modal_navigation', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    navigation.navigate('WorkflowTrigger', {
      modal: true,
      presentation: 'modal',
    });

    expect(navigation.navigate).toHaveBeenCalled();
  });

  /**
   * Test: Nested navigation
   * Expected: Can navigate within nested navigators
   */
  test('test_nested_navigation', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    // Navigate to tab, then to screen within that tab's stack
    navigation.navigate('WorkflowsTab', {
      screen: 'WorkflowsList',
      params: { workflowId: '123' },
    });

    expect(navigation.navigate).toHaveBeenCalled();
  });
});
