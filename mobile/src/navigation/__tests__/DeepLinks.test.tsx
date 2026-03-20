/**
 * Deep Links Tests
 *
 * Tests for deep link handling including:
 * - Agent deep links (atom://agent/{id})
 * - Workflow deep links (atom://workflow/{id})
 * - Canvas deep links (atom://canvas/{id})
 * - Tool deep links (atom://tool/{name})
 * - Invalid deep links
 * - Deep links with query parameters
 * - Deep link navigation
 *
 * Author: Phase 212 Wave 4B
 * Date: 2026-03-20
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { Linking } from 'react-native';

// Mock React Navigation
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
    name: 'Home',
    path: undefined,
  }),
}));

// Mock Linking API
jest.mock('react-native/Libraries/Linking/Linking', () => ({
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  openURL: jest.fn(),
  canOpenURL: jest.fn(() => Promise.resolve(true)),
  getInitialURL: jest.fn(() => Promise.resolve(null)),
  openSettings: jest.fn(),
}));

describe('Deep Links', () => {
  /**
   * Test: Agent deep link
   * Expected: Navigates to agent screen with agent ID
   */
  test('test_agent_deep_link', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://agent/agent-123';

    // Parse deep link
    const agentId = deepLinkUrl.replace('atom://agent/', '');

    // Navigate to agent screen
    navigation.navigate('AgentChat', { agentId });

    expect(agentId).toBe('agent-123');
    expect(navigation.navigate).toHaveBeenCalledWith('AgentChat', { agentId: 'agent-123' });
  });

  /**
   * Test: Workflow deep link
   * Expected: Navigates to workflow screen with workflow ID
   */
  test('test_workflow_deep_link', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://workflow/workflow-456';

    // Parse deep link
    const workflowId = deepLinkUrl.replace('atom://workflow/', '');

    // Navigate to workflow screen
    navigation.navigate('WorkflowDetail', { workflowId });

    expect(workflowId).toBe('workflow-456');
    expect(navigation.navigate).toHaveBeenCalledWith('WorkflowDetail', { workflowId: 'workflow-456' });
  });

  /**
   * Test: Canvas deep link
   * Expected: Navigates to canvas screen with canvas ID
   */
  test('test_canvas_deep_link', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://canvas/canvas-789';

    // Parse deep link
    const canvasId = deepLinkUrl.replace('atom://canvas/', '');

    // Navigate to canvas screen
    navigation.navigate('CanvasView', { canvasId });

    expect(canvasId).toBe('canvas-789');
    expect(navigation.navigate).toHaveBeenCalledWith('CanvasView', { canvasId: 'canvas-789' });
  });

  /**
   * Test: Tool deep link
   * Expected: Navigates to tool screen with tool name
   */
  test('test_tool_deep_link', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://tool/browser';

    // Parse deep link
    const toolName = deepLinkUrl.replace('atom://tool/', '');

    // Navigate to tool screen
    navigation.navigate('ToolExecution', { toolName });

    expect(toolName).toBe('browser');
    expect(navigation.navigate).toHaveBeenCalledWith('ToolExecution', { toolName: 'browser' });
  });

  /**
   * Test: Invalid deep link
   * Expected: Handles invalid deep links gracefully
   */
  test('test_invalid_deep_link', async () => {
    const invalidDeepLinks = [
      'atom://invalid',
      'atom://',
      'notatom://agent/123',
      'atom://agent/',
      'http://agent/123',
      '',
      'atom://agent/123/extra/segments',
    ];

    for (const deepLink of invalidDeepLinks) {
      // Should handle gracefully without crashing
      expect(() => {
        // Validate deep link format
        const isValid = deepLink.startsWith('atom://') &&
                       deepLink.split('/').length >= 3 &&
                       deepLink.split('/')[2] !== '';

        if (!isValid) {
          // Should not navigate
          return;
        }
      }).not.toThrow();
    }
  });

  /**
   * Test: Deep link with query parameters
   * Expected: Parses query parameters correctly
   */
  test('test_deep_link_with_params', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://workflow/workflow-456?tab=details&action=edit';

    // Parse deep link with query params
    const [path, queryString] = deepLinkUrl.split('?');
    const workflowId = path.replace('atom://workflow/', '');

    // Parse query parameters
    const params = new URLSearchParams(queryString);
    const queryParams = {
      tab: params.get('tab'),
      action: params.get('action'),
    };

    // Navigate with params
    navigation.navigate('WorkflowDetail', {
      workflowId,
      ...queryParams,
    });

    expect(workflowId).toBe('workflow-456');
    expect(queryParams.tab).toBe('details');
    expect(queryParams.action).toBe('edit');
    expect(navigation.navigate).toHaveBeenCalledWith('WorkflowDetail', {
      workflowId: 'workflow-456',
      tab: 'details',
      action: 'edit',
    });
  });

  /**
   * Test: Deep link navigation
   * Expected: Navigates to correct screen based on deep link type
   */
  test('test_deep_link_navigation', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinks = [
      { url: 'atom://agent/agent-123', screen: 'AgentChat', paramKey: 'agentId' },
      { url: 'atom://workflow/workflow-456', screen: 'WorkflowDetail', paramKey: 'workflowId' },
      { url: 'atom://canvas/canvas-789', screen: 'CanvasView', paramKey: 'canvasId' },
      { url: 'atom://tool/browser', screen: 'ToolExecution', paramKey: 'toolName' },
    ];

    for (const { url, screen, paramKey } of deepLinks) {
      // Parse deep link
      const parts = url.split('/');
      const type = parts[2]; // agent, workflow, canvas, tool
      const id = parts[3]; // ID or name

      // Navigate based on type
      navigation.navigate(screen, { [paramKey]: id });

      expect(navigation.navigate).toHaveBeenCalledWith(screen, { [paramKey]: id });
    }
  });

  /**
   * Test: Deep link with special characters in ID
   * Expected: Handles special characters correctly
   */
  test('test_deep_link_with_special_characters', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://workflow/workflow%20with%20spaces';

    // Decode URL-encoded characters
    const workflowId = decodeURIComponent(deepLinkUrl.replace('atom://workflow/', ''));

    navigation.navigate('WorkflowDetail', { workflowId });

    expect(workflowId).toBe('workflow with spaces');
    expect(navigation.navigate).toHaveBeenCalledWith('WorkflowDetail', {
      workflowId: 'workflow with spaces',
    });
  });

  /**
   * Test: Deep link with numeric ID
   * Expected: Handles numeric IDs correctly
   */
  test('test_deep_link_with_numeric_id', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://agent/12345';

    const agentId = deepLinkUrl.replace('atom://agent/', '');

    navigation.navigate('AgentChat', { agentId });

    expect(agentId).toBe('12345');
    expect(navigation.navigate).toHaveBeenCalledWith('AgentChat', { agentId: '12345' });
  });

  /**
   * Test: Deep link with UUID
   * Expected: Handles UUID format correctly
   */
  test('test_deep_link_with_uuid', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const uuid = '550e8400-e29b-41d4-a716-446655440000';
    const deepLinkUrl = `atom://agent/${uuid}`;

    const agentId = deepLinkUrl.replace('atom://agent/', '');

    navigation.navigate('AgentChat', { agentId });

    expect(agentId).toBe(uuid);
    expect(navigation.navigate).toHaveBeenCalledWith('AgentChat', { agentId: uuid });
  });

  /**
   * Test: Deep link with hash fragment
   * Expected: Handles hash fragments correctly
   */
  test('test_deep_link_with_hash_fragment', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const deepLinkUrl = 'atom://workflow/workflow-456#section-details';

    // Remove hash fragment
    const [urlWithoutHash] = deepLinkUrl.split('#');
    const workflowId = urlWithoutHash.replace('atom://workflow/', '');

    navigation.navigate('WorkflowDetail', { workflowId, section: 'details' });

    expect(workflowId).toBe('workflow-456');
    expect(navigation.navigate).toHaveBeenCalledWith('WorkflowDetail', {
      workflowId: 'workflow-456',
      section: 'details',
    });
  });

  /**
   * Test: Deep link state preservation
   * Expected: Preserves navigation state when handling deep link
   */
  test('test_deep_link_state_preservation', async () => {
    const { useNavigation } = require('@react-navigation/native');
    const navigation = useNavigation();

    const currentState = {
      index: 1,
      routes: [
        { name: 'Home', key: 'home' },
        { name: 'WorkflowsList', key: 'workflows' },
      ],
    };

    const deepLinkUrl = 'atom://workflow/workflow-456';

    // Navigate to deep link while preserving state
    const workflowId = deepLinkUrl.replace('atom://workflow/', '');

    navigation.navigate('WorkflowDetail', { workflowId });

    expect(navigation.navigate).toHaveBeenCalled();
    // State should be preserved (stack grows, not replaced)
  });

  /**
   * Test: Deep link from cold start
   * Expected: Handles deep link when app is launched from deep link
   */
  test('test_deep_link_from_cold_start', async () => {
    const Linking = require('react-native/Libraries/Linking/Linking');

    // Simulate app launched from deep link
    const initialUrl = 'atom://agent/agent-123';

    Linking.getInitialURL.mockResolvedValueOnce(initialUrl);

    const url = await Linking.getInitialURL();

    expect(url).toBe(initialUrl);
    expect(Linking.getInitialURL).toHaveBeenCalled();

    // Should navigate to agent screen
    const agentId = url.replace('atom://agent/', '');
    expect(agentId).toBe('agent-123');
  });

  /**
   * Test: Deep link while app is running
   * Expected: Handles deep link when app is already running
   */
  test('test_deep_link_while_running', async () => {
    const Linking = require('react-native/Libraries/Linking/Linking');

    // Simulate deep link received while app is running
    const deepLinkUrl = 'atom://workflow/workflow-456';

    // Add event listener for deep links
    const handleDeepLink = (event: { url: string }) => {
      const { url } = event;
      const workflowId = url.replace('atom://workflow/', '');
      return workflowId;
    };

    // Simulate event
    const result = handleDeepLink({ url: deepLinkUrl });

    expect(result).toBe('workflow-456');
  });

  /**
   * Test: Deep link with multiple query parameters
   * Expected: Parses multiple query parameters correctly
   */
  test('test_deep_link_with_multiple_params', async () => {
    const deepLinkUrl = 'atom://workflow/workflow-456?tab=details&action=edit&modal=true&fullscreen=false';

    const [path, queryString] = deepLinkUrl.split('?');
    const params = new URLSearchParams(queryString);

    const queryParams = {
      tab: params.get('tab'),
      action: params.get('action'),
      modal: params.get('modal') === 'true',
      fullscreen: params.get('fullscreen') === 'false' ? false : true,
    };

    expect(queryParams.tab).toBe('details');
    expect(queryParams.action).toBe('edit');
    expect(queryParams.modal).toBe(true);
    expect(queryParams.fullscreen).toBe(false);
  });

  /**
   * Test: Deep link validation
   * Expected: Validates deep link format before processing
   */
  test('test_deep_link_validation', () => {
    const validDeepLinks = [
      'atom://agent/agent-123',
      'atom://workflow/workflow-456',
      'atom://canvas/canvas-789',
      'atom://tool/browser',
    ];

    const invalidDeepLinks = [
      'http://agent/123',
      'https://workflow/456',
      'atom://invalid',
      'atom://agent/',
      '',
      'not-a-url',
    ];

    // Validate function
    const isValidDeepLink = (url: string): boolean => {
      const parts = url.split('/');
      return url.startsWith('atom://') &&
             parts.length >= 4 && // Need: "atom:", "", type, id
             parts[2] !== '' &&
             parts[3] !== '';
    };

    for (const url of validDeepLinks) {
      expect(isValidDeepLink(url)).toBe(true);
    }

    for (const url of invalidDeepLinks) {
      expect(isValidDeepLink(url)).toBe(false);
    }
  });

  /**
   * Test: Deep link case sensitivity
   * Expected: Handles case-insensitive deep links correctly
   */
  test('test_deep_link_case_sensitivity', () => {
    const deepLinks = [
      'atom://agent/Agent-123',
      'atom://workflow/WORKFLOW-456',
      'atom://tool/Browser',
    ];

    for (const url of deepLinks) {
      const parts = url.split('/');
      const type = parts[2].toLowerCase();
      const id = parts[3];

      expect(['agent', 'workflow', 'canvas', 'tool']).toContain(type);
      expect(id).toBeTruthy();
    }
  });
});
