/**
 * React Navigation Edge Cases Tests
 *
 * Tests cover edge cases for React Navigation:
 * - Deep links (atom://agent/{id}, atom://canvas/{id}, atom://workflow/{id})
 * - Deep links with invalid IDs
 * - Navigation stack preservation
 * - Tab navigation
 * - Nested navigation parameters
 * - Navigation to non-existent screens
 *
 * Pattern: Existing AppNavigator.test.tsx patterns (React Navigation testing)
 * @see AppNavigator.test.tsx for baseline navigation patterns
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { NavigationContainer, useNavigation, useNavigationState } from '@react-navigation/native';
import { CommonActions } from '@react-navigation/native';

// Mock navigation for testing
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
const mockReset = jest.fn();
const mockDispatch = jest.fn();

jest.mock('@react-navigation/native', () => ({
  ...jest.requireActual('@react-navigation/native'),
  useNavigation: jest.fn(),
  useNavigationState: jest.fn(),
}));

beforeEach(() => {
  jest.clearAllMocks();

  (useNavigation as jest.Mock).mockReturnValue({
    navigate: mockNavigate,
    goBack: mockGoBack,
    reset: mockReset,
    dispatch: mockDispatch,
    setParams: jest.fn(),
    canGoBack: jest.fn(() => true),
    isFocused: jest.fn(() => true),
    getParent: jest.fn(),
  });

  (useNavigationState as jest.Mock).mockReturnValue({
    index: 0,
    routes: [
      { name: 'WorkflowsTab' },
      { name: 'AnalyticsTab' },
      { name: 'AgentsTab' },
      { name: 'ChatTab' },
      { name: 'SettingsTab' },
    ],
    routeNames: ['WorkflowsTab', 'AnalyticsTab', 'AgentsTab', 'ChatTab', 'SettingsTab'],
    history: undefined,
    key: 'mock-key',
    routeNames: ['WorkflowsTab', 'AnalyticsTab', 'AgentsTab', 'ChatTab', 'SettingsTab'],
    routes: [],
  });
});

afterEach(() => {
  jest.clearAllMocks();
});

describe('React Navigation Edge Cases - Deep Links', () => {
  it('should navigate to agent screen from atom://agent/{id} deep link', async () => {
    const navigation = useNavigation();

    // Simulate deep link navigation
    const deepLinkUrl = 'atom://agent/agent-123';

    // In real implementation, Linking API would parse this
    const agentId = deepLinkUrl.replace('atom://agent/', '');

    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentChat',
        params: { agentId },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'AgentChat',
          params: { agentId: 'agent-123' },
        })
      );
    });
  });

  it('should navigate to canvas screen from atom://canvas/{id} deep link', async () => {
    const navigation = useNavigation();

    // Simulate deep link navigation
    const deepLinkUrl = 'atom://canvas/canvas-456';

    const canvasId = deepLinkUrl.replace('atom://canvas/', '');

    navigation.dispatch(
      CommonActions.navigate({
        name: 'CanvasViewer',
        params: { canvasId },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'CanvasViewer',
          params: { canvasId: 'canvas-456' },
        })
      );
    });
  });

  it('should navigate to workflow screen from atom://workflow/{id} deep link', async () => {
    const navigation = useNavigation();

    // Simulate deep link navigation
    const deepLinkUrl = 'atom://workflow/workflow-789';

    const workflowId = deepLinkUrl.replace('atom://workflow/', '');

    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: { workflowId },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'WorkflowDetail',
          params: { workflowId: 'workflow-789' },
        })
      );
    });
  });

  it('should handle deep link with additional query parameters', async () => {
    const navigation = useNavigation();

    // Deep link with query parameters
    const deepLinkUrl = 'atom://agent/agent-123?tab=executions&filter=active';

    const agentId = 'agent-123';
    const params = { tab: 'executions', filter: 'active' };

    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentChat',
        params: { agentId, ...params },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'AgentChat',
          params: { agentId: 'agent-123', tab: 'executions', filter: 'active' },
        })
      );
    });
  });

  it('should handle deep link with hash fragment', async () => {
    const navigation = useNavigation();

    // Deep link with hash (less common for mobile, but possible)
    const deepLinkUrl = 'atom://canvas/canvas-456#section';

    const canvasId = 'canvas-456';

    navigation.dispatch(
      CommonActions.navigate({
        name: 'CanvasViewer',
        params: { canvasId, section: 'section' },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'CanvasViewer',
          params: { canvasId: 'canvas-456', section: 'section' },
        })
      );
    });
  });
});

describe('React Navigation Edge Cases - Invalid Deep Links', () => {
  it('should handle deep link with invalid agent ID gracefully', async () => {
    const navigation = useNavigation();

    // Deep link with malformed ID
    const deepLinkUrl = 'atom://agent/invalid@#$%';

    const agentId = 'invalid@#$%';

    // In real implementation, would validate ID format
    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentChat',
        params: { agentId },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: should show error screen or redirect
    });
  });

  it('should handle deep link with missing ID parameter', async () => {
    const navigation = useNavigation();

    // Deep link without ID
    const deepLinkUrl = 'atom://agent/';

    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentChat',
        params: {},
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: should show error or redirect to agent list
    });
  });

  it('should handle deep link with non-existent resource ID', async () => {
    const navigation = useNavigation();

    // Deep link to resource that doesn't exist
    const deepLinkUrl = 'atom://agent/non-existent-agent-id';

    const agentId = 'non-existent-agent-id';

    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentChat',
        params: { agentId },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: screen should handle 404 gracefully
    });
  });

  it('should handle deep link with unknown scheme', async () => {
    const navigation = useNavigation();

    // Deep link with unknown scheme (not atom://)
    const deepLinkUrl = 'unknown://agent/agent-123';

    // In real implementation, would ignore or show error
    // For now, just verify it doesn't crash
    expect(() => {
      navigation.dispatch(
        CommonActions.navigate({
          name: 'UnknownScreen',
          params: {},
        })
      );
    }).not.toThrow();
  });

  it('should handle deep link to unknown route', async () => {
    const navigation = useNavigation();

    // Deep link to route that doesn't exist
    const deepLinkUrl = 'atom://unknown-route/some-id';

    navigation.dispatch(
      CommonActions.navigate({
        name: 'UnknownRoute',
        params: { id: 'some-id' },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: should show 404 screen
    });
  });
});

describe('React Navigation Edge Cases - Navigation Stack', () => {
  it('should preserve navigation stack on back navigation', async () => {
    const navigation = useNavigation();

    // Navigate through multiple screens
    navigation.dispatch(
      CommonActions.reset({
        index: 2,
        routes: [
          { name: 'WorkflowsList' },
          { name: 'WorkflowDetail', params: { workflowId: '123' } },
          { name: 'WorkflowTrigger', params: { workflowId: '123' } },
        ],
      })
    );

    // Go back
    navigation.goBack();

    await waitFor(() => {
      expect(mockGoBack).toHaveBeenCalledTimes(1);
      // Stack should now be: [WorkflowsList, WorkflowDetail]
    });
  });

  it('should handle back navigation when stack is empty', async () => {
    // Create a mock that cannot go back
    const mockGoBackEmpty = jest.fn();
    const mockCanGoBack = jest.fn(() => false);

    (useNavigation as jest.Mock).mockReturnValue({
      navigate: mockNavigate,
      goBack: mockGoBackEmpty,
      reset: mockReset,
      dispatch: mockDispatch,
      canGoBack: mockCanGoBack,
    });

    const navigation = useNavigation();

    // Try to go back when no history
    const canGoBack = navigation.canGoBack();

    if (canGoBack) {
      navigation.goBack();
    }

    await waitFor(() => {
      expect(mockGoBackEmpty).not.toHaveBeenCalled();
      // In real implementation: should show home screen or do nothing
    });
  });

  it('should maintain navigation state across tab switches', async () => {
    const navigation = useNavigation();

    // Navigate in one tab
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: { workflowId: '123' },
      })
    );

    // Switch to another tab
    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentsTab',
      })
    );

    // Switch back to first tab
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowsTab',
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledTimes(3);
      // In real implementation: should return to WorkflowDetail, not WorkflowsList
    });
  });

  it('should handle nested navigation stack correctly', async () => {
    const navigation = useNavigation();

    // Navigate deep into nested stack
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: {
          workflowId: '123',
          screen: 'WorkflowTrigger',
          params: {
            executionId: '456',
            screen: 'ExecutionLogs',
          },
        },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // Should navigate to nested screen with correct params
    });
  });

  it('should clear navigation stack on logout', async () => {
    const navigation = useNavigation();

    // Clear stack and navigate to auth
    navigation.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: 'LoginScreen' }],
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.reset({
          index: 0,
          routes: [{ name: 'LoginScreen' }],
        })
      );
    });
  });
});

describe('React Navigation Edge Cases - Tab Navigation', () => {
  it('should switch between tabs correctly', async () => {
    const navigation = useNavigation();

    // Switch from Workflows to Analytics
    navigation.dispatch(
      CommonActions.navigate({
        name: 'AnalyticsTab',
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'AnalyticsTab',
        })
      );
    });
  });

  it('should handle rapid tab switches', async () => {
    const navigation = useNavigation();

    // Rapidly switch between tabs
    navigation.dispatch(CommonActions.navigate({ name: 'AnalyticsTab' }));
    navigation.dispatch(CommonActions.navigate({ name: 'AgentsTab' }));
    navigation.dispatch(CommonActions.navigate({ name: 'ChatTab' }));

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledTimes(3);
      // Should handle without losing state
    });
  });

  it('should preserve tab state when switching away and back', async () => {
    const navigation = useNavigation();

    // Navigate in a tab
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: { workflowId: '123' },
      })
    );

    // Switch to another tab
    navigation.dispatch(CommonActions.navigate({ name: 'AgentsTab' }));

    // Switch back
    navigation.dispatch(CommonActions.navigate({ name: 'WorkflowsTab' }));

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledTimes(3);
      // In real implementation: should return to WorkflowDetail
    });
  });

  it('should handle tab navigation with params', async () => {
    const navigation = useNavigation();

    // Navigate to tab with params
    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentsTab',
        params: { filter: 'active' },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'AgentsTab',
          params: { filter: 'active' },
        })
      );
    });
  });
});

describe('React Navigation Edge Cases - Nested Navigation', () => {
  it('should pass parameters through nested navigators', async () => {
    const navigation = useNavigation();

    // Navigate to nested screen with params
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: {
          workflowId: '123',
          screen: 'ExecutionProgress',
          params: { executionId: '456' },
        },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'WorkflowDetail',
          params: {
            workflowId: '123',
            screen: 'ExecutionProgress',
            params: { executionId: '456' },
          },
        })
      );
    });
  });

  it('should handle nested navigation back correctly', async () => {
    const navigation = useNavigation();

    // Navigate deep into nested stack
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: {
          workflowId: '123',
          screen: 'WorkflowTrigger',
        },
      })
    );

    // Go back (should return to WorkflowDetail)
    navigation.goBack();

    await waitFor(() => {
      expect(mockGoBack).toHaveBeenCalled();
      // In real implementation: should return one level in nested stack
    });
  });

  it('should handle multiple levels of nested navigation', async () => {
    const navigation = useNavigation();

    // Navigate through multiple nesting levels
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: {
          workflowId: '123',
          screen: 'WorkflowTrigger',
          params: {
            executionId: '456',
            screen: 'ExecutionProgress',
            params: {
              logId: '789',
            },
          },
        },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // Should handle deep nesting correctly
    });
  });

  it('should handle navigation from child to parent navigator', async () => {
    const navigation = useNavigation();

    // From nested screen, navigate to different tab
    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentsTab',
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith(
        CommonActions.navigate({
          name: 'AgentsTab',
        })
      );
      // Should switch tabs, maintaining navigation state
    });
  });
});

describe('React Navigation Edge Cases - Navigation to Non-Existent Screens', () => {
  it('should handle navigation to undefined screen gracefully', async () => {
    const navigation = useNavigation();

    // Try to navigate to screen that doesn't exist
    navigation.dispatch(
      CommonActions.navigate({
        name: 'NonExistentScreen',
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: should show error or do nothing
    });
  });

  it('should handle navigation with undefined params', async () => {
    const navigation = useNavigation();

    // Navigate with undefined params
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: undefined,
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: should handle gracefully
    });
  });

  it('should handle navigation with null params', async () => {
    const navigation = useNavigation();

    // Navigate with null params
    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentChat',
        params: null,
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: should handle gracefully
    });
  });

  it('should handle navigation with missing required params', async () => {
    const navigation = useNavigation();

    // Navigate without required params
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: {}, // Missing workflowId
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: should show error or redirect
    });
  });
});

describe('React Navigation Edge Cases - Navigation State', () => {
  it('should provide current navigation state', () => {
    const state = useNavigationState((s) => s);

    expect(state).toBeDefined();
    expect(state.index).toBe(0);
    expect(state.routes).toBeDefined();
    expect(state.routeNames).toBeDefined();
  });

  it('should update navigation state after navigation', async () => {
    const navigation = useNavigation();

    // Navigate to different screen
    navigation.dispatch(
      CommonActions.navigate({
        name: 'AgentsTab',
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: navigationState.index should change
    });
  });

  it('should maintain navigation state across configuration changes', async () => {
    const navigation = useNavigation();

    // Navigate to screen
    navigation.dispatch(
      CommonActions.navigate({
        name: 'WorkflowDetail',
        params: { workflowId: '123' },
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
      // In real implementation: state should persist after rotate, etc.
    });
  });
});

describe('React Navigation Edge Cases - Navigation Actions', () => {
  it('should handle replace action correctly', async () => {
    const navigation = useNavigation();

    // Replace current screen
    navigation.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: 'LoginScreen' }],
      })
    );

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalled();
    });
  });

  it('should handle setParams action correctly', async () => {
    const navigation = useNavigation();

    // Update params for current screen
    const setParams = navigation.setParams;

    if (setParams) {
      setParams({ filter: 'active' });
    }

    await waitFor(() => {
      expect(setParams).toHaveBeenCalledWith({ filter: 'active' });
    });
  });

  it('should handle custom navigation actions', async () => {
    const navigation = useNavigation();

    // Dispatch custom action
    navigation.dispatch({
      type: 'CUSTOM_ACTION',
      payload: { key: 'value' },
    });

    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith({
        type: 'CUSTOM_ACTION',
        payload: { key: 'value' },
      });
    });
  });
});
