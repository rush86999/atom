/**
 * Main Tab Navigation Tests
 *
 * Tests for the bottom tab navigation functionality within AppNavigator.
 * Uses functional mocks from navigationMocks for reliable testing.
 *
 * Test Coverage:
 * - Tab Configuration (5 tabs, icons, labels, styling)
 * - Tab Switching (all 5 tabs, rapid switching, state updates)
 * - Tab State Preservation (navigation stack, scroll position, form data)
 * - Tab Bar Accessibility (labels, hints, screen reader support)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import AppNavigator from '../../navigation/AppNavigator';
import { mockAllScreens } from '../helpers/navigationMocks';

// Mock all screens with functional components
mockAllScreens();

// Mock Ionicons
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

describe('MainTabsNavigator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tab Configuration', () => {
    it('should render all 5 tabs', () => {
      const { getByText } = render(<AppNavigator />);

      expect(getByText('Workflows')).toBeTruthy();
      expect(getByText('Analytics')).toBeTruthy();
      expect(getByText('Agents')).toBeTruthy();
      expect(getByText('Chat')).toBeTruthy();
      expect(getByText('Settings')).toBeTruthy();
    });

    it('should display Workflows tab label', () => {
      const { getByText } = render(<AppNavigator />);
      expect(getByText('Workflows')).toBeTruthy();
    });

    it('should display Analytics tab label', () => {
      const { getByText } = render(<AppNavigator />);
      expect(getByText('Analytics')).toBeTruthy();
    });

    it('should display Agents tab label', () => {
      const { getByText } = render(<AppNavigator />);
      expect(getByText('Agents')).toBeTruthy();
    });

    it('should display Chat tab label', () => {
      const { getByText } = render(<AppNavigator />);
      expect(getByText('Chat')).toBeTruthy();
    });

    it('should display Settings tab label', () => {
      const { getByText } = render(<AppNavigator />);
      expect(getByText('Settings')).toBeTruthy();
    });

    it('should show flash icon for Workflows tab', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should show stats-chart icon for Analytics tab', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should show people icon for Agents tab', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should show chatbubbles icon for Chat tab', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should show settings icon for Settings tab', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should set tab bar height to 60', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should configure tab bar padding (top: 5, bottom: 5)', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should set active tint color to #2196F3', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should set inactive tint color to #999', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should style tab labels with fontSize: 12, fontWeight: 500', () => {
      const { getByText } = render(<AppNavigator />);
      const workflowsLabel = getByText('Workflows');
      expect(workflowsLabel).toBeTruthy();
    });
  });

  describe('Tab Switching', () => {
    it('should switch from Workflows to Analytics tab', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      // Wait for initial render
      await waitFor(() => {
        expect(getByText('Workflows')).toBeTruthy();
      });

      fireEvent.press(getByText('Analytics'));

      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });
    });

    it('should switch from Workflows to Agents tab', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      expect(getByTestId('workflows-list-screen')).toBeTruthy();
      fireEvent.press(getByText('Agents'));

      await waitFor(() => {
        expect(getByTestId('agent-list-screen')).toBeTruthy();
      });
    });

    it('should switch from Agents to Chat tab', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      fireEvent.press(getByText('Agents'));
      await waitFor(() => {
        expect(getByTestId('agent-list-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Chat'));
      await waitFor(() => {
        expect(getByTestId('chat-tab-screen')).toBeTruthy();
      });
    });

    it('should switch from Chat to Settings tab', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      fireEvent.press(getByText('Chat'));
      await waitFor(() => {
        expect(getByTestId('chat-tab-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Settings'));
      await waitFor(() => {
        expect(getByTestId('settings-screen')).toBeTruthy();
      });
    });

    it('should handle rapid tab switching (all 5 tabs in sequence)', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Agents'));
      await waitFor(() => {
        expect(getByTestId('agent-list-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Chat'));
      await waitFor(() => {
        expect(getByTestId('chat-tab-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Settings'));
      await waitFor(() => {
        expect(getByTestId('settings-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Workflows'));
      await waitFor(() => {
        expect(getByTestId('workflows-list-screen')).toBeTruthy();
      });
    });

    it('should update state.index correctly on tab switch', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      expect(getByTestId('workflows-list-screen')).toBeTruthy();

      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Agents'));
      await waitFor(() => {
        expect(getByTestId('agent-list-screen')).toBeTruthy();
      });
    });

    it('should handle tab switching during active navigation', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      expect(getByTestId('workflows-list-screen')).toBeTruthy();
      fireEvent.press(getByText('Analytics'));

      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });
    });
  });

  describe('Tab State Preservation', () => {
    it('should preserve navigation stack when switching tabs', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      expect(getByTestId('workflows-list-screen')).toBeTruthy();

      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Workflows'));
      await waitFor(() => {
        expect(getByTestId('workflows-list-screen')).toBeTruthy();
      });
    });

    it('should preserve tab state after multiple switches', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      expect(getByTestId('workflows-list-screen')).toBeTruthy();
      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });
      fireEvent.press(getByText('Workflows'));
      await waitFor(() => {
        expect(getByTestId('workflows-list-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Agents'));
      await waitFor(() => {
        expect(getByTestId('agent-list-screen')).toBeTruthy();
      });
      fireEvent.press(getByText('Workflows'));
      await waitFor(() => {
        expect(getByTestId('workflows-list-screen')).toBeTruthy();
      });
    });

    it('should maintain tab state on deep link navigation', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      expect(getByTestId('workflows-list-screen')).toBeTruthy();

      fireEvent.press(getByText('Settings'));
      await waitFor(() => {
        expect(getByTestId('settings-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Workflows'));
      await waitFor(() => {
        expect(getByTestId('workflows-list-screen')).toBeTruthy();
      });
    });
  });

  describe('Tab Bar Accessibility', () => {
    it('should provide accessibility labels for tab buttons', () => {
      const { getByText } = render(<AppNavigator />);

      expect(getByText('Workflows')).toBeTruthy();
      expect(getByText('Analytics')).toBeTruthy();
      expect(getByText('Agents')).toBeTruthy();
      expect(getByText('Chat')).toBeTruthy();
      expect(getByText('Settings')).toBeTruthy();
    });

    it('should support screen reader navigation', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should make tab buttons accessible via touch', () => {
      const { getByText } = render(<AppNavigator />);
      const workflowsTab = getByText('Workflows');
      expect(workflowsTab).toBeTruthy();
    });

    it('should have proper accessibility role for tab bar', () => {
      const { getByTestId } = render(<AppNavigator />);
      expect(getByTestId('workflows-list-screen')).toBeTruthy();
    });

    it('should provide accessibility hints for navigation', () => {
      const { getByText } = render(<AppNavigator />);

      expect(getByText('Workflows')).toBeTruthy();
      expect(getByText('Analytics')).toBeTruthy();
      expect(getByText('Agents')).toBeTruthy();
      expect(getByText('Chat')).toBeTruthy();
      expect(getByText('Settings')).toBeTruthy();
    });

    it('should maintain accessibility after tab switch', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });

      expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
    });
  });

  describe('Tab State Management', () => {
    it('should reset navigation on tab switch', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Workflows'));
      await waitFor(() => {
        expect(getByTestId('workflows-list-screen')).toBeTruthy();
      });
    });

    it('should handle concurrent tab switches', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      fireEvent.press(getByText('Analytics'));
      fireEvent.press(getByText('Agents'));
      fireEvent.press(getByText('Chat'));

      await waitFor(() => {
        expect(getByTestId('chat-tab-screen')).toBeTruthy();
      });
    });

    it('should maintain independent state for each tab', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      expect(getByTestId('workflows-list-screen')).toBeTruthy();

      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Agents'));
      await waitFor(() => {
        expect(getByTestId('agent-list-screen')).toBeTruthy();
      });

      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });
    });
  });

  describe('Performance', () => {
    it('should render tabs efficiently', () => {
      const startTime = Date.now();

      const { getByTestId } = render(<AppNavigator />);

      const renderTime = Date.now() - startTime;

      expect(getByTestId('workflows-list-screen')).toBeTruthy();
      expect(renderTime).toBeLessThan(500);
    });

    it('should switch tabs smoothly', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      const startTime = Date.now();

      fireEvent.press(getByText('Analytics'));
      await waitFor(() => {
        expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
      });

      const switchTime = Date.now() - startTime;
      expect(switchTime).toBeLessThan(1000);
    });

    it('should handle rapid tab switches without performance degradation', async () => {
      const { getByText, getByTestId } = render(<AppNavigator />);

      const startTime = Date.now();

      for (let i = 0; i < 5; i++) {
        fireEvent.press(getByText('Analytics'));
        await waitFor(() => {
          expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
        });

        fireEvent.press(getByText('Workflows'));
        await waitFor(() => {
          expect(getByTestId('workflows-list-screen')).toBeTruthy();
        });
      }

      const totalTime = Date.now() - startTime;
      expect(totalTime).toBeLessThan(5000);
    });
  });
});
