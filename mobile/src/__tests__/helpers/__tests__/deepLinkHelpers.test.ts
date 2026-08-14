/**
 * deepLinkHelpers Unit Tests
 *
 * Covers URL parsing, building, validation, param extraction, and the
 * full deep-link inventory generator used by navigation tests.
 */

import {
  DEEP_LINK_PATHS,
  parseDeepLinkURL,
  createDeepLinkTest,
  buildDeepLinkURL,
  buildHTTPSLink,
  validateDeepLinkURL,
  extractRouteParams,
  getAllTestDeepLinks,
} from '../deepLinkHelpers';

describe('parseDeepLinkURL', () => {
  it('parses an atom:// link into components', () => {
    const parsed = parseDeepLinkURL('atom://workflow/abc123?source=email');
    expect(parsed.path).toBe('workflow/abc123');
    expect(parsed.pathSegments).toEqual(['workflow', 'abc123']);
    expect(parsed.queryParams).toEqual({ source: 'email' });
  });

  it('parses an https://atom.ai link with hostname', () => {
    const parsed = parseDeepLinkURL('https://atom.ai/agents');
    expect(parsed.path).toBe('agents');
    expect(parsed.hostname).toBe('atom.ai');
    expect(parsed.pathSegments).toEqual(['agents']);
  });

  it('returns empty pathSegments when no path present', () => {
    const parsed = parseDeepLinkURL('atom://');
    expect(parsed.pathSegments).toEqual([]);
  });
});

describe('createDeepLinkTest / buildDeepLinkURL / buildHTTPSLink', () => {
  it('creates atom:// links with params substituted', () => {
    expect(createDeepLinkTest(DEEP_LINK_PATHS.WORKFLOW_DETAIL, { workflowId: 'w1' }))
      .toBe('atom://workflow/w1');
  });

  it('creates a link without params', () => {
    expect(createDeepLinkTest(DEEP_LINK_PATHS.AUTH_LOGIN)).toBe('atom://auth/login');
  });

  it('buildDeepLinkURL supports custom prefixes and multiple params', () => {
    expect(buildDeepLinkURL('agent/:agentId', { agentId: 'a9' }, 'https://atom.ai/'))
      .toBe('https://atom.ai/agent/a9');
    expect(buildDeepLinkURL(DEEP_LINK_PATHS.WORKFLOW_TRIGGER, { workflowId: 'w2' }))
      .toBe('atom://workflow/w2/trigger');
  });

  it('buildHTTPSLink uses the https://atom.ai/ prefix', () => {
    expect(buildHTTPSLink(DEEP_LINK_PATHS.AUTH_LOGIN)).toBe('https://atom.ai/auth/login');
    expect(buildHTTPSLink(DEEP_LINK_PATHS.EXECUTION_LOGS, { executionId: 'e1' }))
      .toBe('https://atom.ai/execution/e1/logs');
  });
});

describe('validateDeepLinkURL', () => {
  it('accepts atom:// links', () => {
    expect(validateDeepLinkURL('atom://auth/login')).toBe(true);
  });

  it('accepts https://atom.ai links with and without trailing slash', () => {
    expect(validateDeepLinkURL('https://atom.ai/workflows')).toBe(true);
    expect(validateDeepLinkURL('https://atom.ai/chat')).toBe(true);
  });

  it('rejects invalid prefixes', () => {
    expect(validateDeepLinkURL('invalid://path')).toBe(false);
    expect(validateDeepLinkURL('https://evil.com/atom.ai')).toBe(false);
  });

  it('rejects empty paths', () => {
    expect(validateDeepLinkURL('atom://')).toBe(false);
    expect(validateDeepLinkURL('https://atom.ai/')).toBe(false);
    expect(validateDeepLinkURL('https://atom.ai')).toBe(false);
  });
});

describe('extractRouteParams', () => {
  it('extracts params matching the pattern', () => {
    const params = extractRouteParams(
      'atom://workflow/abc123/trigger',
      'workflow/:workflowId/trigger'
    );
    expect(params).toEqual({ workflowId: 'abc123' });
  });

  it('skips param segments with no corresponding path segment', () => {
    const params = extractRouteParams('atom://agent/xyz', 'agent/:agentId/:extra');
    expect(params).toEqual({ agentId: 'xyz' });
  });

  it('returns empty object for patterns without params', () => {
    expect(extractRouteParams('atom://chat', DEEP_LINK_PATHS.CHAT)).toEqual({});
  });
});

describe('getAllTestDeepLinks', () => {
  it('returns a link for every route in both prefixes', () => {
    const links = getAllTestDeepLinks();
    expect(links).toHaveLength(26);

    // Auth routes: atom:// only (4)
    expect(links).toContain('atom://auth/login');
    expect(links).toContain('atom://auth/register');
    expect(links).toContain('atom://auth/reset');
    expect(links).toContain('atom://auth/biometric');

    // Main tabs: both prefixes (10)
    expect(links).toContain('atom://workflows');
    expect(links).toContain('https://atom.ai/workflows');
    expect(links).toContain('https://atom.ai/settings');

    // Resource links with params: both prefixes (12)
    expect(links).toContain('atom://workflow/test-workflow-123');
    expect(links).toContain('https://atom.ai/workflow/test-workflow-123');
    expect(links).toContain('https://atom.ai/execution/test-execution-456/logs');
    expect(links).toContain('atom://agent/test-agent-789');
    expect(links).toContain('https://atom.ai/chat/test-conversation-012');
  });

  it('returns links that all pass validation', () => {
    getAllTestDeepLinks().forEach((link) => {
      expect(validateDeepLinkURL(link)).toBe(true);
    });
  });
});
