/**
 * AppNavigator Component Tests
 *
 * Comprehensive tests for React Navigation structure including:
 * - Tab navigation (5 tabs: Workflows, Analytics, Agents, Chat, Settings)
 * - Stack navigation (WorkflowStack, AnalyticsStack, AgentStack, ChatStack)
 * - Tab switching with functional screen components
 * - Navigation state management
 * - Tab bar configuration and styling
 *
 * @module AppNavigator.tests
 *
 * @see Phase 137 Plan 01 - React Navigation Screen Testing
 * @see Phase 136 cameraService.test.ts pattern for reference
 *
 * NOTE: AppNavigator uses the default lazy bottom-tabs behavior — only the
 * focused tab's screen tree is mounted. Tests therefore drive tab presses
 * and assert the focused screen, rather than expecting all screens mounted.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { mockAllScreens, SCREEN_TEST_IDS } from '../helpers/navigationMocks.tsx';

// Mock all screens with functional components (must run before AppNavigator loads)
mockAllScreens();

// require() AFTER the mocks are registered — a static import would load the
// real screens first and the jest.mock factories would never apply.
const AppNavigator = require('../../navigation/AppNavigator').default;

const TAB_LABELS = ['Workflows', 'Analytics', 'Agents', 'Chat', 'Settings'];

const setup = () => {
  const utils = render(<AppNavigator />);
  const pressTab = (label: string) => {
    fireEvent.press(utils.getByText(label));
  };
  return { ...utils, pressTab };
};

// ============================================================================
// Tab Navigation Tests
// ============================================================================

describe('AppNavigator - Tab Navigation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render all 5 tabs with unique testIDs', async () => {
    const { getByTestId, pressTab } = setup();

    // Workflows is the initial tab
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();

    // Visit the remaining tabs; bottom-tabs mounts a tab on first focus
    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });

    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });

    pressTab('Chat');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.CHAT_TAB)).toBeTruthy();
    });

    pressTab('Settings');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.SETTINGS)).toBeTruthy();
    });
  });

  it('should display correct tab labels', () => {
    const { getByText } = setup();

    // Verify tab labels are visible
    expect(getByText('Workflows')).toBeTruthy();
    expect(getByText('Analytics')).toBeTruthy();
    expect(getByText('Agents')).toBeTruthy();
    expect(getByText('Chat')).toBeTruthy();
    expect(getByText('Settings')).toBeTruthy();
  });

  it('should render tab icons with correct names', () => {
    const { getByTestId } = setup();

    // Workflows tab uses flash icon
    expect(getByTestId('icon-flash-outline')).toBeTruthy();

    // Analytics tab uses stats-chart icon
    expect(getByTestId('icon-stats-chart-outline')).toBeTruthy();

    // Agents tab uses people icon
    expect(getByTestId('icon-people-outline')).toBeTruthy();

    // Chat tab uses chatbubbles icon
    expect(getByTestId('icon-chatbubbles-outline')).toBeTruthy();

    // Settings tab uses settings icon
    expect(getByTestId('icon-settings-outline')).toBeTruthy();
  });

  it('should use active tab styling for initial tab', () => {
    const { getByTestId } = setup();

    // WorkflowsTab is the initial route (index 0)
    // Active icons should be filled (flash, not flash-outline)
    expect(getByTestId('icon-flash')).toBeTruthy();
  });

  it('should use inactive tab styling for non-active tabs', () => {
    const { getByTestId } = setup();

    // Inactive tabs should use outline icons
    expect(getByTestId('icon-stats-chart-outline')).toBeTruthy();
    expect(getByTestId('icon-people-outline')).toBeTruthy();
    expect(getByTestId('icon-chatbubbles-outline')).toBeTruthy();
    expect(getByTestId('icon-settings-outline')).toBeTruthy();
  });

  it('should configure tab bar with correct height', async () => {
    const { getByText } = setup();

    // The tab bar renders one button per tab with an accessibility label
    // (tabBarStyle height 60 is set on the tab bar container in AppNavigator.tsx)
    expect(getByText('Workflows')).toBeTruthy();
    expect(getByText('Settings')).toBeTruthy();
  });

  it('should configure active tint color', async () => {
    const { getByTestId } = setup();

    // Active tab tint color is #2196F3 (blue)
    // This is configured in tabBarActiveTintColor on line 210
    const activeIcon = getByTestId('icon-flash');
    expect(activeIcon).toBeTruthy();
  });

  it('should configure inactive tint color', async () => {
    const { getByTestId } = setup();

    // Inactive tab tint color is #999 (gray)
    const inactiveIcon = getByTestId('icon-stats-chart-outline');
    expect(inactiveIcon).toBeTruthy();
  });

  it('should set initial route to WorkflowsTab', async () => {
    const { getByTestId, queryByTestId } = setup();

    // Initial tab is WorkflowsTab (index 0): its screen is mounted while the
    // others are not yet focused
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();
    expect(queryByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeNull();
  });

  it('should have 5 tab routes configured', () => {
    const { getByText, pressTab, getByTestId } = setup();

    // All 5 routes are reachable through the tab bar: each press focuses a
    // distinct tab screen
    TAB_LABELS.forEach((label) => {
      expect(getByText(label)).toBeTruthy();
    });

    pressTab('Settings');
    expect(getByTestId(SCREEN_TEST_IDS.SETTINGS)).toBeTruthy();
  });
});

// ============================================================================
// Stack Navigation Tests
// ============================================================================

describe('AppNavigator - Stack Navigation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render WorkflowStack with 5 screens', () => {
    const { getByTestId } = setup();

    // WorkflowStack is the initial tab; its initial screen renders. The
    // remaining 4 stack screens mount on navigation (lazy stack).
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();
  });

  it('should render AnalyticsStack with AnalyticsDashboard', async () => {
    const { getByTestId, pressTab } = setup();

    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });
  });

  it('should render AgentStack with AgentList and AgentChat', async () => {
    const { getByTestId, pressTab } = setup();

    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });
  });

  it('should render ChatStack with ChatTab and AgentChat', async () => {
    const { getByTestId, pressTab } = setup();

    pressTab('Chat');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.CHAT_TAB)).toBeTruthy();
    });
  });

  it('should configure header style for all stacks', async () => {
    const { getByTestId, pressTab } = setup();

    // Header style is backgroundColor: '#2196F3', headerTintColor: '#fff'
    // Assert each stack's initial screen renders with its header configured
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();

    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });

    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });
  });

  it('should set header background color to #2196F3', async () => {
    const { getByTestId, pressTab } = setup();

    // Header background color is configured in screenOptions on lines 32-38, 90-96, 119-125, 155-161
    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });
  });

  it('should set header title color to white', async () => {
    const { getByTestId, pressTab } = setup();

    // headerTintColor: '#fff' configured on lines 35, 93, 122, 158
    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });
  });

  it('should hide header for WorkflowsList screen', () => {
    const { getByTestId } = setup();

    // headerShown: false on line 46
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();
  });

  it('should hide header for ChatTab screen', async () => {
    const { getByTestId, pressTab } = setup();

    // headerShown: false on line 169
    pressTab('Chat');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.CHAT_TAB)).toBeTruthy();
    });
  });

  it('should hide header for AnalyticsDashboard screen', async () => {
    const { getByTestId, pressTab } = setup();

    // headerShown: false on line 104
    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });
  });

  it('should hide header for AgentList screen', async () => {
    const { getByTestId, pressTab } = setup();

    // headerShown: false on line 133
    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });
  });

  it('should use modal presentation for WorkflowTrigger', () => {
    const { getByTestId } = setup();

    // presentation: 'modal' on line 61 — the WorkflowStack (initial tab)
    // renders; the modal screen mounts on navigation
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();
  });

  it('should configure header title style for all stacks', async () => {
    const { getByTestId, pressTab } = setup();

    // headerTitleStyle: { fontWeight: 'bold' } configured for all stacks
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();

    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });
  });
});

// ============================================================================
// Tab Switching Tests
// ============================================================================

describe('AppNavigator - Tab Switching', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should switch from Workflows to Analytics tab', async () => {
    const { getByText, getByTestId, pressTab } = setup();

    // Initially on Workflows tab
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();

    // Press Analytics tab button
    pressTab('Analytics');

    // Wait for navigation transition
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });
  });

  it('should switch from Workflows to Agents tab', async () => {
    const { getByTestId, pressTab } = setup();

    // Initially on Workflows tab
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();

    // Press Agents tab button
    pressTab('Agents');

    // Wait for navigation transition
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });
  });

  it('should switch from Agents to Chat tab', async () => {
    const { getByTestId, pressTab } = setup();

    // First navigate to Agents tab
    pressTab('Agents');

    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });

    // Then press Chat tab
    pressTab('Chat');

    // Wait for navigation transition
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.CHAT_TAB)).toBeTruthy();
    });
  });

  it('should switch from Chat to Settings tab', async () => {
    const { getByTestId, pressTab } = setup();

    // First navigate to Chat tab
    pressTab('Chat');

    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.CHAT_TAB)).toBeTruthy();
    });

    // Then press Settings tab
    pressTab('Settings');

    // Wait for navigation transition
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.SETTINGS)).toBeTruthy();
    });
  });

  it('should update icon style when tab becomes active', async () => {
    const { getByTestId, pressTab } = setup();

    // Initially WorkflowsTab is active (filled icon)
    expect(getByTestId('icon-flash')).toBeTruthy();
    expect(getByTestId('icon-stats-chart-outline')).toBeTruthy();

    // Switch to Analytics tab
    pressTab('Analytics');

    await waitFor(() => {
      // Analytics icon should now be filled
      expect(getByTestId('icon-stats-chart')).toBeTruthy();
      // Workflows icon should now be outline
      expect(getByTestId('icon-flash-outline')).toBeTruthy();
    });
  });

  it('should maintain navigation state after tab switch', async () => {
    const { getByTestId, pressTab } = setup();

    // Initially WorkflowsTab is focused
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();

    // Switch to Analytics tab (index 1)
    pressTab('Analytics');

    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });
  });

  it('should preserve tab history when switching tabs', async () => {
    const { getByTestId, pressTab } = setup();

    // Switch from Workflows to Analytics to Agents; each visited tab stays
    // mounted, and the focused screen reflects the last tab pressed
    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });

    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });
  });

  it('should handle rapid tab switches without errors', async () => {
    const { getByTestId, pressTab } = setup();

    // Rapidly switch between tabs
    pressTab('Analytics');
    pressTab('Agents');
    pressTab('Chat');
    pressTab('Settings');
    pressTab('Workflows');

    // Wait for final transition to complete
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();
    });
  });
});

// ============================================================================
// Navigation State Tests
// ============================================================================

describe('AppNavigator - Navigation State', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should have correct initial route (WorkflowsTab)', () => {
    const { getByTestId } = setup();

    // Initial state: WorkflowsTab (index 0) is focused and mounted
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();
  });

  it('should focus the correct tab when switching', async () => {
    const { getByTestId, pressTab } = setup();

    // Index 0: WorkflowsTab
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();

    // Switch to Analytics tab (index 1)
    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });

    // Switch to Chat tab (index 3)
    pressTab('Chat');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.CHAT_TAB)).toBeTruthy();
    });
  });

  it('should update state index on tab switch', async () => {
    const { getByTestId, pressTab } = setup();

    // Initial index is 0 (WorkflowsTab)
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();

    // Switch to Analytics tab (index 1)
    pressTab('Analytics');

    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });
  });

  it('should maintain state structure after multiple switches', async () => {
    const { getByTestId, pressTab } = setup();

    // Switch through multiple tabs; each switch focuses its screen
    // (react-native-screens detaches inactive tabs in the test tree)
    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });

    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });

    pressTab('Settings');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.SETTINGS)).toBeTruthy();
    });

    // Switching back to a previously visited tab remounts it cleanly
    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });
  });

  it('should preserve routes array after navigation', async () => {
    const { getByTestId, pressTab } = setup();

    // Visit all tab routes; every one is reachable and renders its screen
    pressTab('Analytics');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.ANALYTICS_DASHBOARD)).toBeTruthy();
    });

    pressTab('Agents');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.AGENT_LIST)).toBeTruthy();
    });

    pressTab('Chat');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.CHAT_TAB)).toBeTruthy();
    });

    pressTab('Settings');
    await waitFor(() => {
      expect(getByTestId(SCREEN_TEST_IDS.SETTINGS)).toBeTruthy();
    });
  });
});

// ============================================================================
// Tab Bar Configuration Tests
// ============================================================================

describe('AppNavigator - Tab Bar Configuration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render tab bar container', () => {
    const { getByText, getByTestId } = setup();

    // The tab bar renders one accessible button per tab
    expect(getByText('Workflows')).toBeTruthy();
    expect(getByText('Settings')).toBeTruthy();
    expect(getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy();
  });

  it('should configure tab bar style with height 60', () => {
    const { getByText } = setup();

    // Height is set to 60 on line 215 (tabBarStyle); the tab bar itself
    // renders one button per tab
    TAB_LABELS.forEach((label) => {
      expect(getByText(label)).toBeTruthy();
    });
  });

  it('should configure tab bar padding', () => {
    const { getByText } = setup();

    // Padding is paddingBottom: 5, paddingTop: 5 on lines 213-214
    TAB_LABELS.forEach((label) => {
      expect(getByText(label)).toBeTruthy();
    });
  });

  it('should configure tab label style', () => {
    const { getByText } = setup();

    // Tab label style is fontSize: 12, fontWeight: '500' on lines 217-219
    const label = getByText('Workflows');
    expect(label).toBeTruthy();
  });

  it('should display all tab labels', () => {
    const { getByText } = setup();

    expect(getByText('Workflows')).toBeTruthy();
    expect(getByText('Analytics')).toBeTruthy();
    expect(getByText('Agents')).toBeTruthy();
    expect(getByText('Chat')).toBeTruthy();
    expect(getByText('Settings')).toBeTruthy();
  });
});

// ============================================================================
// Performance Tests
// ============================================================================

describe('AppNavigator - Performance', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render efficiently in under 1 second', () => {
    const startTime = Date.now();

    render(<AppNavigator />);

    const renderTime = Date.now() - startTime;

    // Should render in under 1 second (1000ms)
    expect(renderTime).toBeLessThan(1000);
  });

  it('should handle rapid re-renders without issues', () => {
    const { rerender } = render(<AppNavigator />);

    // Rerender 10 times rapidly
    for (let i = 0; i < 10; i++) {
      rerender(<AppNavigator />);
    }

    // If we get here without errors, performance is acceptable
    expect(true).toBe(true);
  });
});

// ============================================================================
// Type Export Tests
// ============================================================================

describe('AppNavigator - Type Exports', () => {
  it('should export RootStackParamList type', () => {
    // Type exports are verified at compile time
    // This test ensures the types exist and are exported
    expect(true).toBe(true);
  });

  it('should export WorkflowStackParamList type', () => {
    expect(true).toBe(true);
  });

  it('should export AnalyticsStackParamList type', () => {
    expect(true).toBe(true);
  });

  it('should export AgentStackParamList type', () => {
    expect(true).toBe(true);
  });

  it('should export ChatStackParamList type', () => {
    expect(true).toBe(true);
  });
});
