/**
 * Navigation Mock Helpers
 *
 * Helper functions for creating functional screen mock components for navigation testing.
 * Replaces string mocks with React components that have testIDs for proper testing.
 *
 * @module navigationMocks
 *
 * @example
 * import { mockAllScreens } from './navigationMocks';
 *
 * mockAllScreens();
 *
 * @see Phase 136 deviceMocks.ts pattern for reference
 */

import React from 'react';
import { View, Text } from 'react-native';

// ============================================================================
// TypeScript Interfaces
// ============================================================================

/**
 * Props for mock screen components
 */
interface MockScreenProps {
  route?: any;
  navigation?: any;
  children?: React.ReactNode;
}

/**
 * Options for creating mock screen
 */
export interface MockScreenOptions {
  /** Custom testID (default: screen-{name.toLowerCase()}) */
  testId?: string;
  /** Include screen name in rendered output */
  showName?: boolean;
  /** Custom component to render */
  customComponent?: React.ComponentType<any>;
}

// ============================================================================
// Mock Screen Factory
// ============================================================================

/**
 * Create a functional mock screen component with testID
 *
 * @param screenName - Name of the screen (for testID and display)
 * @param options - Configuration options
 * @returns React functional component
 *
 * @example
 * const MockScreen = createMockScreen('WorkflowsList', { testId: 'workflows-list-screen' });
 *
 * jest.mock('../../screens/workflows/WorkflowsListScreen', () => MockScreen);
 */
export const createMockScreen = (
  screenName: string,
  options: MockScreenOptions = {}
) => {
  const {
    testId,
    showName = false,
    customComponent: CustomComponent,
  } = options;

  // Generate default testID from screen name
  const defaultTestId = testId || `screen-${screenName.toLowerCase().replace(/\s+/g, '-')}`;

  return function MockScreen(props: MockScreenProps) {
    const { route, navigation } = props;

    return (
      <View testID={defaultTestId} style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        {showName && (
          <Text testID={`${defaultTestId}-name`}>{screenName}</Text>
        )}
        {CustomComponent ? <CustomComponent route={route} navigation={navigation} /> : null}
        {route?.params && (
          <Text testID={`${defaultTestId}-params`} style={{ display: 'none' }}>
            {JSON.stringify(route.params)}
          </Text>
        )}
      </View>
    );
  };
};

/**
 * Create a mock screen with custom render function
 *
 * @param screenName - Name of the screen
 * @param renderFn - Custom render function
 * @returns React functional component
 *
 * @example
 * const CustomScreen = createMockScreenWithRender('CustomScreen', ({ route }) => (
 *   <View><Text>{route.params.id}</Text></View>
 * ));
 */
export const createMockScreenWithRender = (
  screenName: string,
  renderFn: (props: MockScreenProps) => React.ReactNode
) => {
  const testId = `screen-${screenName.toLowerCase().replace(/\s+/g, '-')}`;

  return function MockScreen(props: MockScreenProps) {
    return (
      <View testID={testId} style={{ flex: 1 }}>
        {renderFn(props)}
      </View>
    );
  };
};

// ============================================================================
// Mock All Screens Function
// ============================================================================

/**
 * Mock all screen imports with functional components
 *
 * Call this at the top of your test file to replace all screen imports
 * with functional mock components that have testIDs.
 *
 * @example
 * import { mockAllScreens } from '../helpers/navigationMocks';
 *
 * mockAllScreens();
 */
export const mockAllScreens = () => {
  // Workflow screens
  jest.mock('../../screens/workflows/WorkflowsListScreen', () =>
    createMockScreen('WorkflowsList', { testId: 'workflows-list-screen', showName: true })
  );
  jest.mock('../../screens/workflows/WorkflowDetailScreen', () =>
    createMockScreen('WorkflowDetail', { testId: 'workflow-detail-screen' })
  );
  jest.mock('../../screens/workflows/WorkflowTriggerScreen', () =>
    createMockScreen('WorkflowTrigger', { testId: 'workflow-trigger-screen' })
  );
  jest.mock('../../screens/workflows/ExecutionProgressScreen', () =>
    createMockScreen('ExecutionProgress', { testId: 'execution-progress-screen' })
  );
  jest.mock('../../screens/workflows/WorkflowLogsScreen', () =>
    createMockScreen('WorkflowLogs', { testId: 'workflow-logs-screen' })
  );

  // Analytics screens
  jest.mock('../../screens/analytics/AnalyticsDashboardScreen', () =>
    createMockScreen('AnalyticsDashboard', { testId: 'analytics-dashboard-screen', showName: true })
  );

  // Agent screens
  jest.mock('../../screens/agent/AgentListScreen', () =>
    createMockScreen('AgentList', { testId: 'agent-list-screen', showName: true })
  );
  jest.mock('../../screens/agent/AgentChatScreen', () =>
    createMockScreen('AgentChat', { testId: 'agent-chat-screen' })
  );

  // Chat screens (barrel export)
  jest.mock('../../screens/chat', () => ({
    ChatTabScreen: createMockScreen('ChatTab', { testId: 'chat-tab-screen', showName: true }),
  }));

  // Settings screens
  jest.mock('../../screens/settings/SettingsScreen', () =>
    createMockScreen('Settings', { testId: 'settings-screen', showName: true })
  );
};

// ============================================================================
// Screen TestID Constants
// ============================================================================

/**
 * TestIDs for all mocked screens
 * Use these in tests to query for specific screens
 */
export const SCREEN_TEST_IDS = {
  // Tab screens
  WORKFLOWS_LIST: 'workflows-list-screen',
  ANALYTICS_DASHBOARD: 'analytics-dashboard-screen',
  AGENT_LIST: 'agent-list-screen',
  CHAT_TAB: 'chat-tab-screen',
  SETTINGS: 'settings-screen',

  // Stack screens (WorkflowStack)
  WORKFLOW_DETAIL: 'workflow-detail-screen',
  WORKFLOW_TRIGGER: 'workflow-trigger-screen',
  EXECUTION_PROGRESS: 'execution-progress-screen',
  WORKFLOW_LOGS: 'workflow-logs-screen',

  // Stack screens (AgentStack, ChatStack)
  AGENT_CHAT: 'agent-chat-screen',
} as const;

// ============================================================================
// Tab Icon Mock Helpers
// ============================================================================

/**
 * Mock Ionicons component for testing
 *
 * @example
 * import { mockIonicons } from '../helpers/navigationMocks';
 *
 * mockIonicons();
 */
export const mockIonicons = () => {
  jest.mock('@expo/vector-icons', () => ({
    Ionicons: ({ name, testID }: { name: string; testID?: string }) => {
      return React.createElement('View', {
        testID: testID || `icon-${name}`,
        'data-icon-name': name,
      });
    },
  }));
};

// ============================================================================
// Navigation Mock Helpers
// ============================================================================

/**
 * Create a mock navigation object
 *
 * @param options - Navigation mock options
 * @returns Mock navigation object
 *
 * @example
 * const mockNav = createMockNavigation();
 * mockNav.navigate('WorkflowDetail', { workflowId: '123' });
 */
export const createMockNavigation = (options: {
  canGoBack?: boolean;
  navigate?: jest.Mock;
  goBack?: jest.Mock;
  reset?: jest.Mock;
  dispatch?: jest.Mock;
} = {}) => {
  const {
    canGoBack = true,
    navigate = jest.fn(),
    goBack = jest.fn(),
    reset = jest.fn(),
    dispatch = jest.fn(),
  } = options;

  return {
    canGoBack: () => canGoBack,
    navigate,
    goBack,
    reset,
    dispatch,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    isFocused: jest.fn(() => true),
    setOptions: jest.fn(),
    setParams: jest.fn(),
  };
};

/**
 * Create a mock route object
 *
 * @param params - Route params
 * @returns Mock route object
 *
 * @example
 * const mockRoute = createMockRoute({ workflowId: '123', step: 2 });
 */
export const createMockRoute = (params: Record<string, unknown> = {}) => {
  return {
    key: 'mock-route',
    name: 'MockRoute',
    params,
    path: undefined,
  };
};

// ============================================================================
// Tab Bar Mock Helpers
// ============================================================================

/**
 * TestIDs for tab bar elements
 */
export const TAB_BAR_TEST_IDS = {
  TAB_BAR: 'tab-bar',
  TAB_BUTTON: (tabName: string) => `tab-button-${tabName.toLowerCase()}`,
  TAB_LABEL: (tabName: string) => `tab-label-${tabName.toLowerCase()}`,
  TAB_ICON: (iconName: string) => `icon-${iconName}`,
} as const;

/**
 * Get testID for a tab button
 *
 * @param tabName - Name of the tab (WorkflowsTab, AnalyticsTab, etc.)
 * @returns testID string
 *
 * @example
 * const workflowsTabTestId = getTabButtonTestId('WorkflowsTab');
 * // Returns: 'tab-button-workflowstab'
 */
export const getTabButtonTestId = (tabName: string): string => {
  return `tab-button-${tabName.toLowerCase()}`;
};

// ============================================================================
// Navigation State Helpers
// ============================================================================

/**
 * Create a mock navigation state
 *
 * @param options - State options
 * @returns Mock navigation state object
 *
 * @example
 * const mockState = createMockNavigationState({
 *   index: 1,
 *   routeNames: ['WorkflowsTab', 'AnalyticsTab'],
 *   routes: [{ name: 'WorkflowsTab' }, { name: 'AnalyticsTab' }]
 * });
 */
export const createMockNavigationState = (options: {
  index?: number;
  routeNames?: string[];
  routes?: Array<{ name: string; params?: unknown }>;
  history?: unknown[];
  key?: string;
  type?: string;
} = {}) => {
  const {
    index = 0,
    routeNames = ['WorkflowsTab'],
    routes = [{ name: 'WorkflowsTab' }],
    history = [],
    key = 'mock-state',
    type = 'tab',
  } = options;

  return {
    index,
    routeNames,
    routes,
    history,
    key,
    type,
    stale: false,
  };
};

// ============================================================================
// Exports
// ============================================================================

export default {
  createMockScreen,
  createMockScreenWithRender,
  mockAllScreens,
  mockIonicons,
  createMockNavigation,
  createMockRoute,
  createMockNavigationState,
  SCREEN_TEST_IDS,
  TAB_BAR_TEST_IDS,
  getTabButtonTestId,
};
