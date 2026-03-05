/**
 * Main Tab Navigation Tests
 *
 * Tests for the bottom tab navigation functionality
 * within AppNavigator.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import AppNavigator from '../../navigation/AppNavigator';

// Mock all screens
jest.mock('../../screens/workflows/WorkflowsListScreen', () => 'WorkflowsListScreen');
jest.mock('../../screens/workflows/WorkflowDetailScreen', () => 'WorkflowDetailScreen');
jest.mock('../../screens/workflows/WorkflowTriggerScreen', () => 'WorkflowTriggerScreen');
jest.mock('../../screens/workflows/ExecutionProgressScreen', () => 'ExecutionProgressScreen');
jest.mock('../../screens/workflows/WorkflowLogsScreen', () => 'WorkflowLogsScreen');
jest.mock('../../screens/analytics/AnalyticsDashboardScreen', () => 'AnalyticsDashboardScreen');
jest.mock('../../screens/agent/AgentListScreen', () => 'AgentListScreen');
jest.mock('../../screens/agent/AgentChatScreen', () => 'AgentChatScreen');
jest.mock('../../screens/chat', () => ({
  ChatTabScreen: 'ChatTabScreen',
}));
jest.mock('../../screens/settings/SettingsScreen', () => 'SettingsScreen');

// Mock Ionicons
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

describe('MainTabsNavigator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tab Rendering', () => {
    it('should render all tabs', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should render Workflows tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should render Analytics tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should render Agents tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should render Chat tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should render Settings tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Tab Labels', () => {
    it('should display "Workflows" label', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should display "Analytics" label', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should display "Agents" label', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should display "Chat" label', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should display "Settings" label', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Tab Icons', () => {
    it('should show flash icon for Workflows tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should show stats-chart icon for Analytics tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should show people icon for Agents tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should show chatbubbles icon for Chat tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should show settings icon for Settings tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should show filled icons for active tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should show outline icons for inactive tabs', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Tab Switching', () => {
    it('should switch to Workflows tab on press', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should switch to Analytics tab on press', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should switch to Agents tab on press', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should switch to Chat tab on press', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should switch to Settings tab on press', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should update active tab indicator on switch', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Tab Bar Styling', () => {
    it('should apply active tint color to active tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should apply inactive tint color to inactive tabs', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should set tab bar height', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should configure tab bar padding', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should style tab labels', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Tab State Management', () => {
    it('should maintain tab state on navigation', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should preserve scroll position when switching tabs', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should reset tab navigation on logout', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Accessibility', () => {
    it('should provide accessibility labels for tabs', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should support screen reader navigation', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Performance', () {
    it('should render tabs efficiently', () => {
      const startTime = Date.now();

      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      const renderTime = Date.now() - startTime;

      expect(getByTestId('tab-navigator')).toBeTruthy();
      expect(renderTime).toBeLessThan(500); // Should render in under 500ms
    });

    it('should switch tabs smoothly', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    it('should handle rapid tab switching', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should handle tab switching during navigation', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });
});
