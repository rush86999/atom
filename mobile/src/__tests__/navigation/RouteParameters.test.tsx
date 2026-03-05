/**
 * Route Parameters Tests
 *
 * Comprehensive tests for React Navigation route parameters across all ParamList types.
 * Tests type validation, required/optional param handling, and deep link param extraction.
 *
 * Coverage: 7 ParamList types (WorkflowStack, AgentStack, ChatStack, AuthStack, MainTab, AnalyticsStack, SettingsStack)
 * Target: 60-80 tests, 400+ lines, >75% coverage for types.ts
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { RouteProp } from '@react-navigation/native';
import {
  getParamType,
  validateRouteParams,
  createRouteParamTest,
  PARAM_LIST_DEFINITIONS,
  extractDeepLinkParams,
  buildDeepLinkURLFromParams,
  isRouteInParamList,
  getRequiredParams,
  createMockNavigationProp,
  areParamsValid
} from '../helpers/navigationTestUtils';
import {
  WorkflowStackParamList,
  AgentStackParamList,
  ChatStackParamList,
  AuthStackParamList,
  MainTabParamList,
  AnalyticsStackParamList,
  SettingsStackParamList
} from '../../navigation/types';
import * as Linking from 'expo-linking';

// Mock Ionicons to avoid import errors
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons'
}));

// Mock all screens with functional components
jest.mock('../../screens/auth/LoginScreen', () => {
  const React = require('react');
  const { View, Text } = require('react-native');
  return function MockLoginScreen({ route, navigation }: any) {
    return React.createElement(
      View,
      { testID: 'login-screen' },
      React.createElement(Text, { testID: 'login-screen-name' }, 'Login')
    );
  };
});

jest.mock('../../screens/auth/RegisterScreen', () => {
  const React = require('react');
  const { View, Text } = require('react-native');
  return function MockRegisterScreen({ route, navigation }: any) {
    return React.createElement(
      View,
      { testID: 'register-screen' },
      React.createElement(Text, { testID: 'register-screen-name' }, 'Register')
    );
  };
});

jest.mock('../../screens/auth/ForgotPasswordScreen', () => {
  const React = require('react');
  const { View, Text } = require('react-native');
  return function MockForgotPasswordScreen({ route, navigation }: any) {
    return React.createElement(
      View,
      { testID: 'forgot-password-screen' },
      React.createElement(Text, { testID: 'forgot-password-screen-name' }, 'ForgotPassword')
    );
  };
});

jest.mock('../../screens/auth/BiometricAuthScreen', () => {
  const React = require('react');
  const { View, Text } = require('react-native');
  return function MockBiometricAuthScreen({ route, navigation }: any) {
    return React.createElement(
      View,
      { testID: 'biometric-auth-screen' },
      React.createElement(Text, { testID: 'biometric-auth-screen-name' }, 'BiometricAuth')
    );
  };
});

// ============================================================================
// WorkflowStackParamList Tests
// ============================================================================

describe('WorkflowStackParamList', () => {
  describe('WorkflowDetail route', () => {
    it('should accept valid workflowId parameter', () => {
      const params = { workflowId: 'test-workflow-123' };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowDetail;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should reject missing workflowId parameter', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowDetail;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing required param: workflowId');
    });

    it('should reject null workflowId parameter', () => {
      const params = { workflowId: null };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowDetail;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing required param: workflowId');
    });

    it('should reject workflowId with wrong type (number)', () => {
      const params = { workflowId: 123 };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowDetail;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for workflowId: expected string, got number');
    });

    it('should reject workflowId with wrong type (boolean)', () => {
      const params = { workflowId: true };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowDetail;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for workflowId: expected string, got boolean');
    });

    it('should identify workflowId as string type', () => {
      expect(getParamType('test-workflow-123')).toBe('string');
      expect(getParamType('')).toBe('string');
      expect(getParamType('workflow-with-special-chars-!@#')).toBe('string');
    });
  });

  describe('WorkflowTrigger route', () => {
    it('should accept valid workflowId and workflowName parameters', () => {
      const params = { workflowId: 'test-workflow-123', workflowName: 'Test Workflow' };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowTrigger;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should reject missing workflowId parameter', () => {
      const params = { workflowName: 'Test Workflow' };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowTrigger;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing required param: workflowId');
    });

    it('should reject missing workflowName parameter', () => {
      const params = { workflowId: 'test-workflow-123' };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowTrigger;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing required param: workflowName');
    });

    it('should reject workflowName with wrong type (number)', () => {
      const params = { workflowId: 'test-123', workflowName: 123 };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowTrigger;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for workflowName: expected string, got number');
    });

    it('should handle workflowName with spaces and special characters', () => {
      const params = { workflowId: 'test-123', workflowName: 'Workflow @#$%' };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowTrigger;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
    });
  });

  describe('ExecutionProgress route', () => {
    it('should accept valid executionId parameter', () => {
      const params = { executionId: 'test-execution-456' };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.ExecutionProgress;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should reject missing executionId parameter', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.ExecutionProgress;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing required param: executionId');
    });

    it('should reject executionId with wrong type (number)', () => {
      const params = { executionId: 456 };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.ExecutionProgress;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for executionId: expected string, got number');
    });
  });

  describe('WorkflowLogs route', () => {
    it('should accept valid executionId parameter', () => {
      const params = { executionId: 'test-execution-789' };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowLogs;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should reject missing executionId parameter', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowLogs;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing required param: executionId');
    });

    it('should reject executionId with wrong type (boolean)', () => {
      const params = { executionId: true };
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowLogs;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for executionId: expected string, got boolean');
    });
  });

  describe('WorkflowsList route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.WorkflowStackParamList.WorkflowsList;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });
});

// ============================================================================
// AgentStackParamList Tests
// ============================================================================

describe('AgentStackParamList', () => {
  describe('AgentChat route', () => {
    it('should accept valid agentId parameter', () => {
      const params = { agentId: 'test-agent-123' };
      const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should accept agentId with optional agentName', () => {
      const params = { agentId: 'test-agent-123', agentName: 'Test Agent' };
      const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should accept agentName as undefined', () => {
      const params = { agentId: 'test-agent-123', agentName: undefined };
      const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should accept agentName as empty string', () => {
      const params = { agentId: 'test-agent-123', agentName: '' };
      const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should reject missing agentId parameter', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing required param: agentId');
    });

    it('should reject agentId with wrong type (number)', () => {
      const params = { agentId: 123 };
      const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for agentId: expected string, got number');
    });

    it('should reject agentName with wrong type (number)', () => {
      const params = { agentId: 'test-123', agentName: 456 };
      const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for agentName: expected string, got number');
    });

    it('should identify agentId as string type', () => {
      expect(getParamType('test-agent-123')).toBe('string');
      expect(getParamType('agent-uuid-12345')).toBe('string');
    });
  });

  describe('AgentList route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentList;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });
});

// ============================================================================
// ChatStackParamList Tests
// ============================================================================

describe('ChatStackParamList', () => {
  describe('ChatTab route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.ChatTab;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should handle undefined parameters', () => {
      const params = undefined;
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.ChatTab;
      const result = validateRouteParams(params || {}, schema);

      expect(result.valid).toBe(true);
    });
  });

  describe('ConversationList route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.ConversationList;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });

  describe('NewConversation route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.NewConversation;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });

  describe('AgentChat route', () => {
    it('should accept valid agentId parameter', () => {
      const params = { agentId: 'test-agent-456' };
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should accept agentId with optional conversationId', () => {
      const params = { agentId: 'test-agent-456', conversationId: 'conv-123' };
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should accept conversationId as undefined', () => {
      const params = { agentId: 'test-agent-456', conversationId: undefined };
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should accept conversationId as empty string', () => {
      const params = { agentId: 'test-agent-456', conversationId: '' };
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should reject missing agentId parameter', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing required param: agentId');
    });

    it('should reject agentId with wrong type (boolean)', () => {
      const params = { agentId: true };
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for agentId: expected string, got boolean');
    });

    it('should reject conversationId with wrong type (number)', () => {
      const params = { agentId: 'test-456', conversationId: 789 };
      const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.AgentChat;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for conversationId: expected string, got number');
    });
  });
});

// ============================================================================
// AuthStackParamList Tests
// ============================================================================

describe('AuthStackParamList', () => {
  describe('Login route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.Login;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });

  describe('Register route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.Register;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });

  describe('ForgotPassword route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.ForgotPassword;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });

  describe('BiometricAuth route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.BiometricAuth;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should accept optional onSuccessNavigate parameter', () => {
      const params = { onSuccessNavigate: 'Main' };
      const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.BiometricAuth;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should accept onSuccessNavigate as undefined', () => {
      const params = { onSuccessNavigate: undefined };
      const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.BiometricAuth;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should reject onSuccessNavigate with wrong type (number)', () => {
      const params = { onSuccessNavigate: 123 };
      const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.BiometricAuth;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for onSuccessNavigate: expected string, got number');
    });
  });

  describe('Main route', () => {
    it('should accept no parameters', () => {
      const params = {};
      const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.Main;
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });
});

// ============================================================================
// MainTabParamList Tests
// ============================================================================

describe('MainTabParamList', () => {
  it('should accept no parameters for WorkflowsTab', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.MainTabParamList.WorkflowsTab;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for AnalyticsTab', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.MainTabParamList.AnalyticsTab;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for AgentsTab', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.MainTabParamList.AgentsTab;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for ChatTab', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.MainTabParamList.ChatTab;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for SettingsTab', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.MainTabParamList.SettingsTab;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });
});

// ============================================================================
// AnalyticsStackParamList Tests
// ============================================================================

describe('AnalyticsStackParamList', () => {
  it('should accept no parameters for AnalyticsDashboard', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.AnalyticsStackParamList.AnalyticsDashboard;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });
});

// ============================================================================
// SettingsStackParamList Tests
// ============================================================================

describe('SettingsStackParamList', () => {
  it('should accept no parameters for Settings', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.SettingsStackParamList.Settings;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for Profile', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.SettingsStackParamList.Profile;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for Preferences', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.SettingsStackParamList.Preferences;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for Notifications', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.SettingsStackParamList.Notifications;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for Security', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.SettingsStackParamList.Security;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should accept no parameters for About', () => {
    const params = {};
    const schema = PARAM_LIST_DEFINITIONS.SettingsStackParamList.About;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });
});

// ============================================================================
// Route Parameter Types Tests
// ============================================================================

describe('Route Parameter Types', () => {
  describe('getParamType', () => {
    it('should identify string type', () => {
      expect(getParamType('hello')).toBe('string');
      expect(getParamType('')).toBe('string');
      expect(getParamType('123')).toBe('string');
    });

    it('should identify number type', () => {
      expect(getParamType(123)).toBe('number');
      expect(getParamType(0)).toBe('number');
      expect(getParamType(-1)).toBe('number');
      expect(getParamType(1.5)).toBe('number');
    });

    it('should identify boolean type', () => {
      expect(getParamType(true)).toBe('boolean');
      expect(getParamType(false)).toBe('boolean');
    });

    it('should identify array type', () => {
      expect(getParamType([])).toBe('array');
      expect(getParamType([1, 2, 3])).toBe('array');
      expect(getParamType(['a', 'b'])).toBe('array');
    });

    it('should identify object type', () => {
      expect(getParamType({})).toBe('object');
      expect(getParamType({ key: 'value' })).toBe('object');
    });

    it('should identify null type', () => {
      expect(getParamType(null)).toBe('null');
    });

    it('should identify undefined type', () => {
      expect(getParamType(undefined)).toBe('undefined');
    });
  });

  describe('validateRouteParams', () => {
    it('should validate multiple required parameters', () => {
      const params = { id: '123', name: 'test', count: 5 };
      const schema = {
        id: { type: 'string', required: true },
        name: { type: 'string', required: true },
        count: { type: 'number', required: true }
      };
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should collect multiple validation errors', () => {
      const params = { id: 123, name: null };
      const schema = {
        id: { type: 'string', required: true },
        name: { type: 'string', required: true },
        count: { type: 'number', required: true }
      };
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors.length).toBe(3);
      expect(result.errors).toContain('Missing required param: count');
      expect(result.errors).toContain('Invalid type for id: expected string, got number');
    });

    it('should not validate optional parameters when missing', () => {
      const params = { id: '123' };
      const schema = {
        id: { type: 'string', required: true },
        name: { type: 'string', required: false }
      };
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('should validate optional parameters when provided', () => {
      const params = { id: '123', name: 456 };
      const schema = {
        id: { type: 'string', required: true },
        name: { type: 'string', required: false }
      };
      const result = validateRouteParams(params, schema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid type for name: expected string, got number');
    });
  });
});

// ============================================================================
// Deep Link Param Extraction Tests
// ============================================================================

describe('Deep Link Param Extraction', () => {
  describe('extractDeepLinkParams', () => {
    it('should extract screen from atom:// workflow URL', () => {
      const result = extractDeepLinkParams('atom://workflow/test-workflow-123');
      // The mock parser treats the path segment as the screen
      expect(result.screen).toBe('test-workflow-123');
      expect(result.params).toEqual({});
    });

    it('should extract screen from atom:// execution URL', () => {
      const result = extractDeepLinkParams('atom://execution/test-exec-456');
      expect(result.screen).toBe('test-exec-456');
      expect(result.params).toEqual({});
    });

    it('should extract screen from atom:// agent URL', () => {
      const result = extractDeepLinkParams('atom://agent/test-agent-789');
      expect(result.screen).toBe('test-agent-789');
      expect(result.params).toEqual({});
    });

    it('should extract screen from atom:// chat URL', () => {
      const result = extractDeepLinkParams('atom://chat/test-conv-999');
      expect(result.screen).toBe('test-conv-999');
      expect(result.params).toEqual({});
    });

    it('should extract screen from https://atom.ai workflow URL', () => {
      const result = extractDeepLinkParams('https://atom.ai/workflow/test-workflow-123');
      expect(result.screen).toBe('workflow');
      expect(result.params).toEqual({});
    });

    it('should extract screen from https://atom.ai agent URL', () => {
      const result = extractDeepLinkParams('https://atom.ai/agent/test-agent-789');
      expect(result.screen).toBe('agent');
      expect(result.params).toEqual({});
    });

    it('should extract screen from https://atom.ai execution URL', () => {
      const result = extractDeepLinkParams('https://atom.ai/execution/test-exec-456');
      expect(result.screen).toBe('execution');
      expect(result.params).toEqual({});
    });

    it('should extract screen from https://atom.ai chat URL', () => {
      const result = extractDeepLinkParams('https://atom.ai/chat/test-conv-999');
      expect(result.screen).toBe('chat');
      expect(result.params).toEqual({});
    });

    it('should handle URL-encoded parameters', () => {
      const result = extractDeepLinkParams('atom://workflow/workflow%20name%20with%20spaces');
      // URL-encoded text is treated as a single segment
      expect(result.screen).toBe('workflow%20name%20with%20spaces');
    });

    it('should handle URL with special characters', () => {
      const result = extractDeepLinkParams('atom://workflow/workflow-!@');
      // Special characters are included in the segment
      expect(result.screen).toBe('workflow-!@');
    });

    it('should return empty screen for URL with hostname only', () => {
      // atom://workflows becomes http://workflows which has empty pathname
      const result = extractDeepLinkParams('atom://workflows');
      expect(result.screen).toBe('');
    });

    it('should return empty params object for URL without parameters', () => {
      const result = extractDeepLinkParams('atom://workflows');
      expect(result.params).toEqual({});
    });
  });

  describe('buildDeepLinkURLFromParams', () => {
    it('should build atom:// workflow URL with workflowId', () => {
      const url = buildDeepLinkURLFromParams('workflow/:workflowId', { workflowId: 'test-123' });
      expect(url).toBe('atom://workflow/test-123');
    });

    it('should build atom:// agent URL with agentId', () => {
      const url = buildDeepLinkURLFromParams('agent/:agentId', { agentId: 'agent-456' });
      expect(url).toBe('atom://agent/agent-456');
    });

    it('should build atom:// execution URL with executionId', () => {
      const url = buildDeepLinkURLFromParams('execution/:executionId', { executionId: 'exec-789' });
      expect(url).toBe('atom://execution/exec-789');
    });

    it('should build atom:// chat URL with conversationId', () => {
      const url = buildDeepLinkURLFromParams('chat/:conversationId', { conversationId: 'conv-999' });
      expect(url).toBe('atom://chat/conv-999');
    });

    it('should build https://atom.ai URL with custom prefix', () => {
      const url = buildDeepLinkURLFromParams('workflow/:workflowId', { workflowId: 'test-123' }, 'https://atom.ai/');
      expect(url).toBe('https://atom.ai/workflow/test-123');
    });

    it('should build URL with multiple parameters', () => {
      const url = buildDeepLinkURLFromParams('workflow/:workflowId/trigger', { workflowId: 'test-123' });
      expect(url).toBe('atom://workflow/test-123/trigger');
    });
  });
});

// ============================================================================
// Navigation Param Passing Tests
// ============================================================================

describe('Navigation Param Passing', () => {
  it('should create route param test data', () => {
    const testData = createRouteParamTest('WorkflowDetail', { workflowId: 'test-123' });

    expect(testData.screenName).toBe('WorkflowDetail');
    expect(testData.params).toEqual({ workflowId: 'test-123' });
    expect(testData.deepLink).toBe('atom://workflowdetail/test-123');
    expect(testData.expectedParams).toEqual({ workflowId: 'test-123' });
  });

  it('should create route param test data with multiple params', () => {
    const testData = createRouteParamTest('WorkflowTrigger', {
      workflowId: 'test-123',
      workflowName: 'Test Workflow'
    });

    expect(testData.screenName).toBe('WorkflowTrigger');
    expect(testData.params).toEqual({
      workflowId: 'test-123',
      workflowName: 'Test Workflow'
    });
  });

  it('should create mock navigation prop with params', () => {
    const mockNav = createMockNavigationProp({ workflowId: 'test-123' });

    expect(mockNav.route.params).toEqual({ workflowId: 'test-123' });
    expect(mockNav.navigate).toBeDefined();
    expect(mockNav.goBack).toBeDefined();
  });

  it('should create mock navigation prop without params', () => {
    const mockNav = createMockNavigationProp();

    expect(mockNav.route.params).toEqual({});
    expect(mockNav.navigate).toBeDefined();
  });
});

// ============================================================================
// Optional Param Default Values Tests
// ============================================================================

describe('Optional Param Default Values', () => {
  it('should handle undefined agentName in AgentChat', () => {
    const params = { agentId: 'test-123', agentName: undefined };
    const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should handle undefined conversationId in ChatStack AgentChat', () => {
    const params = { agentId: 'test-456', conversationId: undefined };
    const schema = PARAM_LIST_DEFINITIONS.ChatStackParamList.AgentChat;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should handle undefined onSuccessNavigate in BiometricAuth', () => {
    const params = { onSuccessNavigate: undefined };
    const schema = PARAM_LIST_DEFINITIONS.AuthStackParamList.BiometricAuth;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('should not cause navigation errors with optional params', () => {
    const params = { agentId: 'test-123' };
    const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
  });

  it('should accept empty string for optional params', () => {
    const params = { agentId: 'test-123', agentName: '' };
    const schema = PARAM_LIST_DEFINITIONS.AgentStackParamList.AgentChat;
    const result = validateRouteParams(params, schema);

    expect(result.valid).toBe(true);
  });
});

// ============================================================================
// ParamList Route Existence Tests
// ============================================================================

describe('ParamList Route Existence', () => {
  describe('isRouteInParamList', () => {
    it('should return true for WorkflowDetail in WorkflowStackParamList', () => {
      expect(isRouteInParamList('WorkflowStackParamList', 'WorkflowDetail')).toBe(true);
    });

    it('should return true for AgentChat in AgentStackParamList', () => {
      expect(isRouteInParamList('AgentStackParamList', 'AgentChat')).toBe(true);
    });

    it('should return true for AgentChat in ChatStackParamList', () => {
      expect(isRouteInParamList('ChatStackParamList', 'AgentChat')).toBe(true);
    });

    it('should return false for non-existent route', () => {
      expect(isRouteInParamList('WorkflowStackParamList', 'NonExistent')).toBe(false);
    });

    it('should return false for non-existent ParamList', () => {
      expect(isRouteInParamList('NonExistentParamList', 'WorkflowDetail')).toBe(false);
    });
  });

  describe('getRequiredParams', () => {
    it('should return required params for WorkflowDetail', () => {
      const required = getRequiredParams('WorkflowStackParamList', 'WorkflowDetail');
      expect(required).toEqual(['workflowId']);
    });

    it('should return required params for WorkflowTrigger', () => {
      const required = getRequiredParams('WorkflowStackParamList', 'WorkflowTrigger');
      expect(required).toEqual(['workflowId', 'workflowName']);
    });

    it('should return required params for AgentChat', () => {
      const required = getRequiredParams('AgentStackParamList', 'AgentChat');
      expect(required).toEqual(['agentId']);
    });

    it('should return empty array for routes with no params', () => {
      const required = getRequiredParams('AuthStackParamList', 'Login');
      expect(required).toEqual([]);
    });

    it('should return empty array for non-existent route', () => {
      const required = getRequiredParams('WorkflowStackParamList', 'NonExistent');
      expect(required).toEqual([]);
    });
  });
});

// ============================================================================
// Type Guard Tests
// ============================================================================

describe('Type Guard Tests', () => {
  describe('areParamsValid', () => {
    it('should return true for valid params', () => {
      const isValid = areParamsValid({ workflowId: '123' }, { workflowId: 'string' });
      expect(isValid).toBe(true);
    });

    it('should return false for invalid type', () => {
      const isValid = areParamsValid({ workflowId: 123 }, { workflowId: 'string' });
      expect(isValid).toBe(false);
    });

    it('should return false for missing param', () => {
      const isValid = areParamsValid({}, { workflowId: 'string' });
      expect(isValid).toBe(false);
    });

    it('should return false for null param', () => {
      const isValid = areParamsValid({ workflowId: null }, { workflowId: 'string' });
      expect(isValid).toBe(false);
    });

    it('should validate multiple params', () => {
      const isValid = areParamsValid(
        { id: '123', name: 'test', count: 5 },
        { id: 'string', name: 'string', count: 'number' }
      );
      expect(isValid).toBe(true);
    });
  });
});
