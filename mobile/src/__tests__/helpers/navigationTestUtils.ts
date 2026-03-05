/**
 * Navigation Testing Utilities
 *
 * Helper functions for testing React Navigation route parameters,
 * type validation, and deep link param extraction.
 *
 * Provides utilities for validating ParamList types, checking parameter
 * types, and building test data for route parameter testing.
 */

import * as Linking from 'expo-linking';
import { parseDeepLinkURL } from './deepLinkHelpers';

/**
 * Get the type of a parameter value
 *
 * Returns a string representation of the value's type for validation.
 * Used to ensure route parameters match expected types from ParamList definitions.
 *
 * @param value - Value to check type of
 * @returns Type string ('string', 'number', 'boolean', 'array', 'object', 'null', 'undefined')
 *
 * @example
 * ```typescript
 * getParamType('test'); // 'string'
 * getParamType(123); // 'number'
 * getParamType(true); // 'boolean'
 * getParamType(['a', 'b']); // 'array'
 * getParamType({ key: 'value' }); // 'object'
 * getParamType(null); // 'null'
 * getParamType(undefined); // 'undefined'
 * ```
 */
export const getParamType = (value: unknown): string => {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (typeof value === 'string') return 'string';
  if (typeof value === 'number') return 'number';
  if (typeof value === 'boolean') return 'boolean';
  if (Array.isArray(value)) return 'array';
  return 'object';
};

/**
 * Validate route parameters against expected schema
 *
 * Checks that all required parameters are present and that parameter
 * types match the expected types from ParamList definitions.
 *
 * @param params - Route parameters to validate
 * @param expectedParams - Schema mapping param names to type and required status
 * @returns Validation result with valid flag and array of error messages
 *
 * @example
 * ```typescript
 * const result = validateRouteParams(
 *   { workflowId: 'test-123', agentName: 'Test Agent' },
 *   {
 *     workflowId: { type: 'string', required: true },
 *     agentName: { type: 'string', required: false }
 *   }
 * );
 * // { valid: true, errors: [] }
 *
 * const invalid = validateRouteParams(
 *   { workflowId: 123 },
 *   { workflowId: { type: 'string', required: true } }
 * );
 * // { valid: false, errors: ['Invalid type for workflowId: expected string, got number'] }
 * ```
 */
export const validateRouteParams = (
  params: Record<string, unknown>,
  expectedParams: Record<string, { type: string; required: boolean }>
): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];

  Object.entries(expectedParams).forEach(([key, spec]) => {
    const value = params[key];

    // Check required parameters
    if (spec.required && (value === undefined || value === null)) {
      errors.push(`Missing required param: ${key}`);
      return;
    }

    // Check type if value is provided
    if (value !== undefined && getParamType(value) !== spec.type) {
      errors.push(`Invalid type for ${key}: expected ${spec.type}, got ${getParamType(value)}`);
    }
  });

  return { valid: errors.length === 0, errors };
};

/**
 * Create route parameter test data
 *
 * Generates test data for route parameter testing with screen name,
 * params object, deep link URL, and expected params for validation.
 *
 * @param screenName - Name of the screen/route
 * @param routeParams - Route parameters object
 * @param prefix - Deep link prefix (default: 'atom://')
 * @returns Test data object with screen, params, deep link, and expected params
 *
 * @example
 * ```typescript
 * const test = createRouteParamTest('WorkflowDetail', { workflowId: 'test-123' });
 * // {
 * //   screenName: 'WorkflowDetail',
 * //   params: { workflowId: 'test-123' },
 * //   deepLink: 'atom://workflowdetail/test-123',
 * //   expectedParams: { workflowId: 'test-123' }
 * // }
 * ```
 */
export const createRouteParamTest = (
  screenName: string,
  routeParams: Record<string, string | number | boolean>,
  prefix: string = 'atom://'
) => {
  // Build deep link URL from screen name and params
  const path = screenName.toLowerCase();
  let url = `${prefix}${path}`;

  // Append params as path segments (e.g., atom://workflowdetail/123)
  const paramValues = Object.values(routeParams);
  if (paramValues.length > 0) {
    url += `/${paramValues.join('/')}`;
  }

  return {
    screenName,
    params: routeParams,
    deepLink: url,
    expectedParams: routeParams
  };
};

/**
 * ParamList type definitions for validation
 *
 * Maps each ParamList type to its route definitions with parameter
 * schemas (type and required status). Used for runtime validation
 * of route parameters against TypeScript type definitions.
 *
 * These schemas mirror the TypeScript types from navigation/types.ts:
 * - WorkflowStackParamList: workflowId, workflowName, executionId
 * - AgentStackParamList: agentId, agentName
 * - ChatStackParamList: agentId, conversationId
 * - AuthStackParamList: onSuccessNavigate (optional)
 * - MainTabParamList: no params
 * - AnalyticsStackParamList: no params
 * - SettingsStackParamList: no params
 */
export const PARAM_LIST_DEFINITIONS = {
  WorkflowStackParamList: {
    WorkflowsList: {},
    WorkflowDetail: {
      workflowId: { type: 'string', required: true }
    },
    WorkflowTrigger: {
      workflowId: { type: 'string', required: true },
      workflowName: { type: 'string', required: true }
    },
    ExecutionProgress: {
      executionId: { type: 'string', required: true }
    },
    WorkflowLogs: {
      executionId: { type: 'string', required: true }
    }
  },

  AgentStackParamList: {
    AgentList: {},
    AgentChat: {
      agentId: { type: 'string', required: true },
      agentName: { type: 'string', required: false }
    }
  },

  ChatStackParamList: {
    ChatTab: {},
    ConversationList: {},
    NewConversation: {},
    AgentChat: {
      agentId: { type: 'string', required: true },
      conversationId: { type: 'string', required: false }
    }
  },

  AuthStackParamList: {
    Login: {},
    Register: {},
    ForgotPassword: {},
    BiometricAuth: {
      onSuccessNavigate: { type: 'string', required: false }
    },
    Main: {}
  },

  MainTabParamList: {
    WorkflowsTab: {},
    AnalyticsTab: {},
    AgentsTab: {},
    ChatTab: {},
    SettingsTab: {}
  },

  AnalyticsStackParamList: {
    AnalyticsDashboard: {}
  },

  SettingsStackParamList: {
    Settings: {},
    Profile: {},
    Preferences: {},
    Notifications: {},
    Security: {},
    About: {}
  }
} as const;

/**
 * Extract deep link parameters from URL
 *
 * Parses a deep link URL and extracts route name and parameters.
 * Handles both atom:// and https://atom.ai prefixes, extracting
 * screen name from path and dynamic params from path segments.
 *
 * @param url - Deep link URL to parse
 * @returns Object with screen name and extracted parameters
 *
 * @example
 * ```typescript
 * extractDeepLinkParams('atom://workflow/test-workflow-123');
 * // { screen: 'workflow', params: {} }
 *
 * extractDeepLinkParams('atom://agent/agent-456/agent-name');
 * // { screen: 'agent', params: { '456': 'agent-name' } }
 *
 * extractDeepLinkParams('https://atom.ai/workflow/test-123');
 * // { screen: 'workflow', params: {} }
 * ```
 */
export const extractDeepLinkParams = (url: string): { screen: string; params: Record<string, string> } => {
  const parsed = parseDeepLinkURL(url);
  const segments = parsed.pathSegments;

  // Extract screen from first segment
  const screen = segments[0] || '';

  // Extract params from path segments (e.g., workflow/:workflowId)
  // Pattern: segments after screen are key-value pairs
  const params: Record<string, string> = {};
  for (let i = 1; i < segments.length; i += 2) {
    if (segments[i + 1]) {
      params[segments[i]] = segments[i + 1];
    }
  }

  return { screen, params };
};

/**
 * Build deep link URL with parameters
 *
 * Creates a deep link URL by combining path, parameters, and prefix.
 * Replaces :parameter placeholders with actual values.
 *
 * @param path - Path pattern (e.g., 'workflow/:workflowId')
 * @param params - Parameter values to substitute
 * @param prefix - URL prefix (default: 'atom://')
 * @returns Complete deep link URL
 *
 * @example
 * ```typescript
 * buildDeepLinkURLFromParams('workflow/:workflowId', { workflowId: '123' });
 * // 'atom://workflow/123'
 *
 * buildDeepLinkURLFromParams('agent/:agentId/chat', { agentId: '456' });
 * // 'atom://agent/456/chat'
 * ```
 */
export const buildDeepLinkURLFromParams = (
  path: string,
  params: Record<string, string> = {},
  prefix: string = 'atom://'
): string => {
  let url = `${prefix}${path}`;
  Object.entries(params).forEach(([key, value]) => {
    url = url.replace(`:${key}`, value);
  });
  return url;
};

/**
 * Validate ParamList type at runtime
 *
 * Checks if a route name belongs to a specific ParamList type.
 * Useful for validating that navigation calls use correct routes.
 *
 * @param paramListName - Name of the ParamList (e.g., 'WorkflowStackParamList')
 * @param routeName - Route name to check
 * @returns true if route exists in ParamList, false otherwise
 *
 * @example
 * ```typescript
 * isRouteInParamList('WorkflowStackParamList', 'WorkflowDetail'); // true
 * isRouteInParamList('WorkflowStackParamList', 'NonExistent'); // false
 * ```
 */
export const isRouteInParamList = (
  paramListName: keyof typeof PARAM_LIST_DEFINITIONS,
  routeName: string
): boolean => {
  const paramList = PARAM_LIST_DEFINITIONS[paramListName];
  return paramList && routeName in paramList;
};

/**
 * Get required parameters for a route
 *
 * Returns an array of required parameter names for a specific route.
 * Useful for test setup to ensure all required params are provided.
 *
 * @param paramListName - Name of the ParamList
 * @param routeName - Route name to get required params for
 * @returns Array of required parameter names
 *
 * @example
 * ```typescript
 * getRequiredParams('WorkflowStackParamList', 'WorkflowDetail');
 * // ['workflowId']
 *
 * getRequiredParams('AgentStackParamList', 'AgentChat');
 * // ['agentId']
 * ```
 */
export const getRequiredParams = (
  paramListName: keyof typeof PARAM_LIST_DEFINITIONS,
  routeName: string
): string[] => {
  const paramList = PARAM_LIST_DEFINITIONS[paramListName];
  if (!paramList || !(routeName in paramList)) {
    return [];
  }

  const routeDef = paramList[routeName];
  return Object.entries(routeDef)
    .filter(([_, spec]) => spec.required)
    .map(([key]) => key);
};

/**
 * Create mock navigation prop with params
 *
 * Creates a mock navigation object with route params for testing.
 * Use this to test screens that access navigation params.
 *
 * @param params - Route params to include in mock
 * @returns Mock navigation prop object
 *
 * @example
 * ```typescript
 * const mockNav = createMockNavigationProp({ workflowId: 'test-123' });
 * // Mock screen can access route.params.workflowId
 * ```
 */
export const createMockNavigationProp = (params: Record<string, unknown> = {}) => {
  return {
    navigate: jest.fn(),
    goBack: jest.fn(),
    reset: jest.fn(),
    dispatch: jest.fn(),
    setParams: jest.fn(),
    isFocused: jest.fn(() => true),
    canGoBack: jest.fn(() => false),
    getId: jest.fn(),
    getParent: jest.fn(),
    getState: jest.fn(),
    route: {
      key: 'test-route',
      name: 'TestRoute',
      params
    }
  };
};

/**
 * Type guard for checking if params are valid
 *
 * Runtime type check for route params against a schema.
 * Returns true if params match the schema, false otherwise.
 *
 * @param params - Params to validate
 * @param schema - Schema to validate against
 * @returns true if params are valid
 *
 * @example
 * ```typescript
 * const isValid = areParamsValid(
 *   { workflowId: '123' },
 *   { workflowId: 'string' }
 * ); // true
 *
 * const isInvalid = areParamsValid(
 *   { workflowId: 123 },
 *   { workflowId: 'string' }
 * ); // false
 * ```
 */
export const areParamsValid = (
  params: Record<string, unknown>,
  schema: Record<string, string>
): boolean => {
  return Object.entries(schema).every(([key, expectedType]) => {
    const value = params[key];
    if (value === undefined || value === null) {
      return false;
    }
    return getParamType(value) === expectedType;
  });
};
