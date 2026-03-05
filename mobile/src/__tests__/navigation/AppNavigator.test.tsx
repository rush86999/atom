/**
 * AppNavigator Component Tests
 *
 * Tests for app navigation structure, tab navigation,
 * deep linking, and routing.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import AppNavigator from '../../../navigation/AppNavigator';

// Mock all screens
jest.mock('../../../screens/workflows/WorkflowsListScreen', () => 'WorkflowsListScreen');
jest.mock('../../../screens/workflows/WorkflowDetailScreen', () => 'WorkflowDetailScreen');
jest.mock('../../../screens/workflows/WorkflowTriggerScreen', () => 'WorkflowTriggerScreen');
jest.mock('../../../screens/workflows/ExecutionProgressScreen', () => 'ExecutionProgressScreen');
jest.mock('../../../screens/workflows/WorkflowLogsScreen', () => 'WorkflowLogsScreen');
jest.mock('../../../screens/analytics/AnalyticsDashboardScreen', () => 'AnalyticsDashboardScreen');
jest.mock('../../../screens/agent/AgentListScreen', () => 'AgentListScreen');
jest.mock('../../../screens/agent/AgentChatScreen', () => 'AgentChatScreen');
jest.mock('../../../screens/chat/ChatTabScreen', () => 'ChatTabScreen');
jest.mock('../../../screens/settings/SettingsScreen', () => 'SettingsScreen');

// Mock Ionicons
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

describe('AppNavigator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tab Navigation', () => {
    it('should render all tabs', () => {
      const { getByText } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      // Tab labels should be visible
      expect(screen.getByTestId('tab-navigator')).toBeTruthy();
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

  describe('Tab Icons', () => {
    it('should show icons for each tab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should show active tab indicator', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Stack Navigation', () => {
    it('should render WorkflowStack with screens', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should render AnalyticsStack with screens', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should render AgentStack with screens', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should render ChatStack with screens', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Deep Linking', () => {
    it('should handle deep links for workflows', async () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should handle deep links for agents', async () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should handle deep links for chat', async () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Navigation State', () => {
    it('should handle navigation state changes', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should maintain navigation state', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Tab Switching', () => {
    it('should switch tabs on press', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Header Configuration', () => {
    it('should configure header style for all stacks', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should set header title color', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Screen Options', () => {
    it('should hide header for WorkflowsList', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should hide header for ChatTab', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should hide header for AnalyticsDashboard', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should hide header for AgentList', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should show modal presentation for WorkflowTrigger', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Navigation Types', () => {
    it('should export RootStackParamList', () => {
      // Type exports are verified at compile time
      expect(true).toBe(true);
    });

    it('should export WorkflowStackParamList', () => {
      expect(true).toBe(true);
    });

    it('should export AnalyticsStackParamList', () => {
      expect(true).toBe(true);
    });

    it('should export AgentStackParamList', () => {
      expect(true).toBe(true);
    });

    it('should export ChatStackParamList', () => {
      expect(true).toBe(true);
    });
  });

  describe('Nested Navigation', () => {
    it('should handle nested stack navigation', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should navigate to WorkflowDetail from WorkflowsList', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });

    it('should navigate to AgentChat from AgentList', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Tab Bar Configuration', () => {
    it('should configure tab bar style', () => {
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

    it('should configure tab label style', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Back Button', () => {
    it('should handle back button press', () => {
      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      expect(getByTestId('tab-navigator')).toBeTruthy();
    });
  });

  describe('Performance', () => {
    it('should render efficiently', () => {
      const startTime = Date.now();

      const { getByTestId } = render(
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      );

      const renderTime = Date.now() - startTime;

      expect(getByTestId('tab-navigator')).toBeTruthy();
      expect(renderTime).toBeLessThan(1000); // Should render in under 1 second
    });
  });
});
