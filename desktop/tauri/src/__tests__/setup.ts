/**
 * Test Setup
 * Global test configuration and mocks
 */

import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock Tauri API
vi.mock('@tauri-apps/api/tauri', () => ({
  invoke: vi.fn(),
  emit: vi.fn(),
  listen: vi.fn(),
  removeAllListeners: vi.fn()
}));

// Mock Tauri Window
vi.mock('@tauri-apps/api/window', () => ({
  appWindow: {
    setTitle: vi.fn(),
    setMinSize: vi.fn(),
    setSize: vi.fn()
  }
}));

// Mock Chakra UI
vi.mock('@chakra-ui/react', () => ({
  ...require('@chakra-ui/react'),
  // Mock specific components if needed
}));

// Mock React Icons
vi.mock('react-icons/fi', () => ({
  FiGithub: () => 'FiGithub',
  FiRepo: () => 'FiRepo',
  FiIssue: () => 'FiIssue',
  FiGitPullRequest: () => 'FiGitPullRequest',
  FiPlus: () => 'FiPlus',
  FiEdit3: () => 'FiEdit3',
  FiTrash2: () => 'FiTrash2',
  FiSearch: () => 'FiSearch',
  FiFilter: () => 'FiFilter',
  FiRefresh: () => 'FiRefresh',
  FiCheck: () => 'FiCheck',
  FiX: () => 'FiX',
  FiExternalLink: () => 'FiExternalLink',
  FiSettings: () => 'FiSettings',
  FiUser: () => 'FiUser',
  FiMoreVertical: () => 'FiMoreVertical',
  FiStar: () => 'FiStar',
  FiFork: () => 'FiFork',
  FiActivity: () => 'FiActivity',
  FiLock: () => 'FiLock',
  FiGitMerge: () => 'FiGitMerge',
  FiGitCommit: () => 'FiGitCommit'
}));

// Mock Event Bus
vi.mock('../utils/EventBus', () => ({
  EventBus: {
    on: vi.fn(),
    off: vi.fn(),
    emit: vi.fn()
  }
}));

// Mock Logger
vi.mock('../utils/Logger', () => ({
  Logger: vi.fn().mockImplementation(() => ({
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn()
  }))
}));

// Mock crypto for token encryption
Object.defineProperty(global, 'crypto', {
  value: {
    getRandomValues: vi.fn(() => new Uint8Array(16)),
    subtle: {
      encrypt: vi.fn().mockResolvedValue(new ArrayBuffer(16)),
      decrypt: vi.fn().mockResolvedValue(new ArrayBuffer(16))
    }
  }
});

// Mock localStorage
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
    length: 0,
    key: vi.fn()
  },
  writable: true
});

// Mock fetch API
global.fetch = vi.fn();

// Global test utilities
global.mockTauriInvoke = vi.fn();
global.mockEventBus = {
  on: vi.fn(),
  off: vi.fn(),
  emit: vi.fn()
};
global.mockLogger = {
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  debug: vi.fn()
};

// Test environment setup
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// Performance monitoring
global.testStartTime = Date.now();
global.logTestDuration = (testName: string) => {
  const duration = Date.now() - global.testStartTime;
  console.log(`⏱️ ${testName} completed in ${duration}ms`);
};

// Security test utilities
global.createXSSPayload = () => '<script>alert("xss")</script>';
global.createSQLInjectionPayload = () => "'; DROP TABLE users; --";
global.createPathTraversalPayload = () => '../../../etc/passwd';
global.createCommandInjectionPayload = () => '; rm -rf /';

// Error test utilities
global.createNetworkError = (message: string = 'Network error') => {
  const error = new Error(message);
  error.name = 'NetworkError';
  return error;
};

global.createAPIError = (message: string, status: number = 400) => {
  const error = new Error(message);
  error.name = 'APIError';
  // @ts-ignore
  error.status = status;
  return error;
};

// GitHub test utilities
global.createMockGitHubUser = (overrides = {}) => ({
  id: 12345,
  login: 'mockuser',
  name: 'Mock User',
  email: 'mock@example.com',
  avatar_url: 'https://github.com/mockuser.png',
  company: 'ATOM Company',
  location: 'San Francisco, CA',
  bio: 'Software Developer at ATOM',
  public_repos: 25,
  followers: 150,
  following: 75,
  created_at: '2020-01-01T00:00:00Z',
  updated_at: '2025-11-02T10:00:00Z',
  html_url: 'https://github.com/mockuser',
  type: 'User',
  ...overrides
});

global.createMockGitHubRepo = (overrides = {}) => ({
  id: 123456,
  name: 'mock-repo',
  full_name: 'mockuser/mock-repo',
  description: 'Mock repository for testing',
  private: false,
  fork: false,
  html_url: 'https://github.com/mockuser/mock-repo',
  clone_url: 'https://github.com/mockuser/mock-repo.git',
  ssh_url: 'git@github.com:mockuser/mock-repo.git',
  default_branch: 'main',
  language: 'TypeScript',
  stargazers_count: 42,
  watchers_count: 42,
  forks_count: 15,
  open_issues_count: 8,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2025-11-02T10:00:00Z',
  pushed_at: '2025-11-02T09:00:00Z',
  size: 1024,
  ...overrides
});

global.createMockGitHubIssue = (overrides = {}) => ({
  id: 1001,
  number: 42,
  title: 'Mock Issue',
  body: 'Mock issue for testing',
  state: 'open',
  locked: false,
  user: global.createMockGitHubUser({ login: 'developer1' }),
  assignees: [],
  labels: [{ id: 123, name: 'enhancement', color: 'a2eeef' }],
  created_at: '2025-11-01T10:00:00Z',
  updated_at: '2025-11-02T15:30:00Z',
  html_url: 'https://github.com/mockuser/mock-repo/issues/42',
  repository_url: 'https://api.github.com/repos/mockuser/mock-repo',
  ...overrides
});

global.createMockGitHubPR = (overrides = {}) => ({
  id: 2001,
  number: 15,
  title: 'Mock Pull Request',
  body: 'Mock pull request for testing',
  state: 'open',
  locked: false,
  user: global.createMockGitHubUser({ login: 'contributor1' }),
  assignees: [global.createMockGitHubUser({ login: 'developer1' })],
  requested_reviewers: [global.createMockGitHubUser({ login: 'reviewer1' })],
  labels: [{ id: 234, name: 'feature', color: '0075ca' }],
  comments: 12,
  review_comments: 8,
  commits: 5,
  additions: 1250,
  deletions: 85,
  changed_files: 12,
  created_at: '2025-11-01T08:00:00Z',
  updated_at: '2025-11-02T16:20:00Z',
  mergeable: true,
  html_url: 'https://github.com/mockuser/mock-repo/pull/15',
  diff_url: 'https://github.com/mockuser/mock-repo/pull/15.diff',
  repository_url: 'https://api.github.com/repos/mockuser/mock-repo',
  head: {
    label: 'contributor1:feature/test',
    ref_field: 'feature/test',
    sha: 'abc123def456',
    user: global.createMockGitHubUser({ login: 'contributor1' }),
    repo: global.createMockGitHubRepo()
  },
  base: {
    label: 'mockuser:main',
    ref_field: 'main',
    sha: 'xyz789uvw012',
    user: global.createMockGitHubUser(),
    repo: global.createMockGitHubRepo()
  },
  ...overrides
});

// Console override for cleaner test output
const originalConsoleError = console.error;
console.error = (...args) => {
  // Filter out expected test errors
  if (args[0] && typeof args[0] === 'string' && args[0].includes('Warning')) {
    return;
  }
  originalConsoleError(...args);
};

export {};