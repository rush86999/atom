/**
 * Deep Link Testing Utilities
 *
 * Helper functions for testing React Navigation deep linking with
 * atom:// and https://atom.ai prefixes.
 *
 * Provides URL parsing, building, and validation utilities for all
 * deep link routes configured in AuthNavigator and AppNavigator.
 */

import * as Linking from 'expo-linking';

/**
 * Deep link path constants matching AuthNavigator linking config
 *
 * These paths correspond to the deep link configuration in AuthNavigator.tsx
 * and AppNavigator.tsx for both atom:// and https://atom.ai prefixes.
 */
export const DEEP_LINK_PATHS = {
  // Auth screens
  AUTH_LOGIN: 'auth/login',
  AUTH_REGISTER: 'auth/register',
  AUTH_RESET: 'auth/reset',
  AUTH_BIOMETRIC: 'auth/biometric',

  // Main app screens
  WORKFLOWS: 'workflows',
  ANALYTICS: 'analytics',
  AGENTS: 'agents',
  CHAT: 'chat',
  SETTINGS: 'settings',

  // Resource deep links
  WORKFLOW_DETAIL: 'workflow/:workflowId',
  WORKFLOW_TRIGGER: 'workflow/:workflowId/trigger',
  EXECUTION_PROGRESS: 'execution/:executionId',
  EXECUTION_LOGS: 'execution/:executionId/logs',
  AGENT_DETAIL: 'agent/:agentId',
  CONVERSATION: 'chat/:conversationId',
} as const;

/**
 * Parse a deep link URL into its components
 *
 * Uses expo-linking's Linking.parse() to extract path, hostname,
 * query parameters, and path segments from a deep link URL.
 *
 * @param url - Deep link URL to parse (e.g., "atom://auth/login", "https://atom.ai/workflows")
 * @returns Parsed URL components
 *
 * @example
 * ```typescript
 * const parsed = parseDeepLinkURL('atom://workflow/abc123?source=email');
 * // {
 * //   path: 'workflow/abc123',
 * //   hostname: null,
 * //   queryParams: { source: 'email' },
 * //   pathSegments: ['workflow', 'abc123']
 * // }
 * ```
 */
export const parseDeepLinkURL = (url: string) => {
  const parsed = Linking.parse(url);
  return {
    path: parsed.path,
    hostname: parsed.hostname,
    queryParams: parsed.queryParams,
    pathSegments: parsed.path?.split('/').filter(Boolean) || [],
  };
};

/**
 * Create a deep link test URL by replacing path parameters
 *
 * Replaces :parameter placeholders in a path pattern with actual values.
 * Used for building deep link URLs with dynamic route parameters.
 *
 * @param pattern - Path pattern with :parameter placeholders (e.g., "workflow/:workflowId")
 * @param params - Object mapping parameter names to values (e.g., { workflowId: "abc123" })
 * @returns Deep link URL with atom:// prefix
 *
 * @example
 * ```typescript
 * createDeepLinkTest('workflow/:workflowId', { workflowId: 'abc123' });
 * // Returns: "atom://workflow/abc123"
 * ```
 */
export const createDeepLinkTest = (pattern: string, params: Record<string, string> = {}) => {
  let url = `atom://${pattern}`;
  Object.entries(params).forEach(([key, value]) => {
    url = url.replace(`:${key}`, value);
  });
  return url;
};

/**
 * Build a deep link URL with custom prefix
 *
 * Creates a deep link URL by replacing path parameters and optionally
 * using a custom prefix (default: atom://). Supports both atom:// and
 * https://atom.ai prefixes for testing.
 *
 * @param path - Path pattern with optional :parameter placeholders
 * @param params - Object mapping parameter names to values
 * @param prefix - URL prefix (default: "atom://")
 * @returns Complete deep link URL
 *
 * @example
 * ```typescript
 * buildDeepLinkURL('workflow/:workflowId/trigger', { workflowId: 'abc123' });
 * // Returns: "atom://workflow/abc123/trigger"
 *
 * buildDeepLinkURL('agent/:agentId', { agentId: 'xyz789' }, 'https://atom.ai/');
 * // Returns: "https://atom.ai/agent/xyz789"
 * ```
 */
export const buildDeepLinkURL = (
  path: string,
  params: Record<string, string> = {},
  prefix: string = 'atom://'
) => {
  let url = `${prefix}${path}`;
  Object.entries(params).forEach(([key, value]) => {
    url = url.replace(`:${key}`, value);
  });
  return url;
};

/**
 * Build an HTTPS deep link variant
 *
 * Creates an HTTPS deep link URL using the https://atom.ai prefix.
 * Used for testing that deep links work with both custom schemes
 * and universal links.
 *
 * @param path - Path pattern with optional :parameter placeholders
 * @param params - Object mapping parameter names to values
 * @returns HTTPS deep link URL
 *
 * @example
 * ```typescript
 * buildHTTPSLink('auth/login');
 * // Returns: "https://atom.ai/auth/login"
 *
 * buildHTTPSLink('execution/:executionId/logs', { executionId: 'exec123' });
 * // Returns: "https://atom.ai/execution/exec123/logs"
 * ```
 */
export const buildHTTPSLink = (path: string, params: Record<string, string> = {}) => {
  return buildDeepLinkURL(path, params, 'https://atom.ai/');
};

/**
 * Validate that a deep link URL is properly formatted
 *
 * Checks that a URL has a valid prefix (atom:// or https://atom.ai)
 * and contains a non-empty path.
 *
 * @param url - URL to validate
 * @returns true if URL is valid, false otherwise
 *
 * @example
 * ```typescript
 * validateDeepLinkURL('atom://auth/login'); // true
 * validateDeepLinkURL('https://atom.ai/workflows'); // true
 * validateDeepLinkURL('invalid://path'); // false
 * validateDeepLinkURL('atom://'); // false
 * ```
 */
export const validateDeepLinkURL = (url: string): boolean => {
  const validPrefixes = ['atom://', 'https://atom.ai/', 'https://atom.ai'];
  const hasValidPrefix = validPrefixes.some(prefix => url.startsWith(prefix));

  if (!hasValidPrefix) {
    return false;
  }

  // Extract path after prefix
  let path: string;
  if (url.startsWith('atom://')) {
    path = url.slice(7);
  } else if (url.startsWith('https://atom.ai/')) {
    path = url.slice(18);
  } else {
    path = url.slice(17);
  }

  // Path should not be empty
  return path.length > 0;
};

/**
 * Extract route parameters from a deep link URL
 *
 * Parses a deep link URL and extracts dynamic route parameters
 * based on the expected path pattern.
 *
 * @param url - Deep link URL to parse
 * @param pattern - Path pattern with :parameter placeholders
 * @returns Object mapping parameter names to values
 *
 * @example
 * ```typescript
 * extractRouteParams('atom://workflow/abc123/trigger', 'workflow/:workflowId/trigger');
 * // Returns: { workflowId: 'abc123' }
 *
 * extractRouteParams('atom://execution/exec456/logs', 'execution/:executionId/logs');
 * // Returns: { executionId: 'exec456' }
 * ```
 */
export const extractRouteParams = (
  url: string,
  pattern: string
): Record<string, string> => {
  const parsed = parseDeepLinkURL(url);
  const patternSegments = pattern.split('/').filter(Boolean);
  const pathSegments = parsed.pathSegments;

  const params: Record<string, string> = {};

  patternSegments.forEach((segment, index) => {
    if (segment.startsWith(':') && pathSegments[index]) {
      const paramName = segment.slice(1);
      params[paramName] = pathSegments[index];
    }
  });

  return params;
};

/**
 * Get all test deep link URLs for comprehensive testing
 *
 * Returns an array of all deep link URLs that should be tested,
 * covering all routes in AuthNavigator and AppNavigator with
 * both atom:// and https://atom.ai prefixes.
 *
 * @returns Array of deep link URLs to test
 */
export const getAllTestDeepLinks = (): string[] => {
  const links: string[] = [];

  // Auth screen deep links (atom:// only)
  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.AUTH_LOGIN));
  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.AUTH_REGISTER));
  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.AUTH_RESET));
  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.AUTH_BIOMETRIC));

  // Main app screens (both atom:// and https://atom.ai)
  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.WORKFLOWS));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.WORKFLOWS));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.ANALYTICS));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.ANALYTICS));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.AGENTS));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.AGENTS));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.CHAT));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.CHAT));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.SETTINGS));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.SETTINGS));

  // Resource deep links with parameters (both prefixes)
  const testParams = {
    workflowId: 'test-workflow-123',
    executionId: 'test-execution-456',
    agentId: 'test-agent-789',
    conversationId: 'test-conversation-012',
  };

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.WORKFLOW_DETAIL, testParams));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.WORKFLOW_DETAIL, testParams));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.WORKFLOW_TRIGGER, testParams));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.WORKFLOW_TRIGGER, testParams));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.EXECUTION_PROGRESS, testParams));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.EXECUTION_PROGRESS, testParams));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.EXECUTION_LOGS, testParams));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.EXECUTION_LOGS, testParams));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.AGENT_DETAIL, testParams));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.AGENT_DETAIL, testParams));

  links.push(buildDeepLinkURL(DEEP_LINK_PATHS.CONVERSATION, testParams));
  links.push(buildHTTPSLink(DEEP_LINK_PATHS.CONVERSATION, testParams));

  return links;
};
