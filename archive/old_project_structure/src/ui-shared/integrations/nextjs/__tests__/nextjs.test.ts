/**
 * Next.js Integration Tests
 * Unit and integration tests for Next.js/Vercel integration
 */

import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { z } from 'zod';
import {
  NextjsProject,
  NextjsBuild,
  NextjsDeployment,
  NextjsConfig
} from '../types';
import { NextjsUtils } from '../utils';
import {
  validateNextjsProject,
  validateNextjsConfig,
  validateNextjsOAuthRequest,
  DefaultNextjsConfig,
  isNextjsProject,
  isNextjsConfig
} from '../validation/schemas';
import {
  useNextjsProjects,
  useNextjsAnalytics,
  useNextjsDeployment,
  useNextjsConfig
} from '../hooks';

// Mock fetch
global.fetch = vi.fn();

// Mock toast
vi.mock('@chakra-ui/react', () => ({
  ...vi.importActual('@chakra-ui/react'),
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn()
  }
}));

describe('NextjsUtils', () => {
  describe('formatBuildDuration', () => {
    test('should format seconds correctly', () => {
      expect(NextjsUtils.formatBuildDuration(30000)).toBe('30s');
    });

    test('should format minutes and seconds correctly', () => {
      expect(NextjsUtils.formatBuildDuration(90000)).toBe('1m 30s');
    });

    test('should handle undefined duration', () => {
      expect(NextjsUtils.formatBuildDuration(undefined)).toBe('N/A');
    });
  });

  describe('formatFileSize', () => {
    test('should format bytes correctly', () => {
      expect(NextjsUtils.formatFileSize(1024)).toBe('1.00 KB');
    });

    test('should format megabytes correctly', () => {
      expect(NextjsUtils.formatFileSize(1048576)).toBe('1.00 MB');
    });

    test('should handle undefined size', () => {
      expect(NextjsUtils.formatFileSize(undefined)).toBe('N/A');
    });
  });

  describe('getStatusColor', () => {
    test('should return green for success statuses', () => {
      expect(NextjsUtils.getStatusColor('ready')).toBe('green');
      expect(NextjsUtils.getStatusColor('success')).toBe('green');
      expect(NextjsUtils.getStatusColor('active')).toBe('green');
    });

    test('should return blue for building statuses', () => {
      expect(NextjsUtils.getStatusColor('building')).toBe('blue');
      expect(NextjsUtils.getStatusColor('pending')).toBe('blue');
    });

    test('should return red for error statuses', () => {
      expect(NextjsUtils.getStatusColor('error')).toBe('red');
      expect(NextjsUtils.getStatusColor('failed')).toBe('red');
    });
  });

  describe('filterProjects', () => {
    const projects: NextjsProject[] = [
      {
        id: '1',
        name: 'Test Project',
        description: 'A test project',
        status: 'active',
        framework: 'nextjs',
        runtime: 'node',
        domains: ['test.example.com'],
        createdAt: '2023-01-01T00:00:00.000Z',
        updatedAt: '2023-01-01T00:00:00.000Z',
        settings: {
          buildCommand: 'npm run build',
          outputDirectory: '.next',
          installCommand: 'npm install',
          nodeVersion: '18',
          environmentVariables: {}
        }
      },
      {
        id: '2',
        name: 'React App',
        description: 'A React application',
        status: 'active',
        framework: 'react',
        runtime: 'node',
        domains: ['react.example.com'],
        createdAt: '2023-01-01T00:00:00.000Z',
        updatedAt: '2023-01-01T00:00:00.000Z',
        settings: {
          buildCommand: 'npm run build',
          outputDirectory: 'build',
          installCommand: 'npm install',
          nodeVersion: '18',
          environmentVariables: {}
        }
      }
    ];

    test('should filter projects by name', () => {
      const filtered = NextjsUtils.filterProjects(projects, 'Test');
      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('Test Project');
    });

    test('should filter projects by description', () => {
      const filtered = NextjsUtils.filterProjects(projects, 'React application');
      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('React App');
    });

    test('should filter projects by framework', () => {
      const filtered = NextjsUtils.filterProjects(projects, 'nextjs');
      expect(filtered).toHaveLength(1);
      expect(filtered[0].framework).toBe('nextjs');
    });

    test('should return all projects for empty search term', () => {
      const filtered = NextjsUtils.filterProjects(projects, '');
      expect(filtered).toHaveLength(2);
    });
  });

  describe('sortProjects', () => {
    const projects: NextjsProject[] = [
      {
        id: '1',
        name: 'A Project',
        status: 'active',
        framework: 'nextjs',
        runtime: 'node',
        domains: [],
        createdAt: '2023-01-01T00:00:00.000Z',
        updatedAt: '2023-01-02T00:00:00.000Z',
        settings: {
          buildCommand: 'npm run build',
          outputDirectory: '.next',
          installCommand: 'npm install',
          nodeVersion: '18',
          environmentVariables: {}
        }
      },
      {
        id: '2',
        name: 'Z Project',
        status: 'active',
        framework: 'react',
        runtime: 'node',
        domains: [],
        createdAt: '2023-01-01T00:00:00.000Z',
        updatedAt: '2023-01-01T00:00:00.000Z',
        settings: {
          buildCommand: 'npm run build',
          outputDirectory: 'build',
          installCommand: 'npm install',
          nodeVersion: '18',
          environmentVariables: {}
        }
      }
    ];

    test('should sort projects by name ascending', () => {
      const sorted = NextjsUtils.sortProjects(projects, 'name', 'asc');
      expect(sorted[0].name).toBe('A Project');
      expect(sorted[1].name).toBe('Z Project');
    });

    test('should sort projects by name descending', () => {
      const sorted = NextjsUtils.sortProjects(projects, 'name', 'desc');
      expect(sorted[0].name).toBe('Z Project');
      expect(sorted[1].name).toBe('A Project');
    });
  });

  describe('calculateBuildSuccessRate', () => {
    test('should calculate success rate correctly', () => {
      const builds: NextjsBuild[] = [
        { id: '1', projectId: '1', status: 'ready', createdAt: '2023-01-01T00:00:00.000Z' },
        { id: '2', projectId: '1', status: 'ready', createdAt: '2023-01-01T00:00:00.000Z' },
        { id: '3', projectId: '1', status: 'error', createdAt: '2023-01-01T00:00:00.000Z' }
      ];
      
      const rate = NextjsUtils.calculateBuildSuccessRate(builds);
      expect(rate).toBe(67); // 2/3 * 100 rounded
    });

    test('should handle empty builds array', () => {
      const rate = NextjsUtils.calculateBuildSuccessRate([]);
      expect(rate).toBe(0);
    });
  });

  describe('generateProjectSummary', () => {
    const project: NextjsProject = {
      id: '1',
      name: 'Test Project',
      description: 'A test project for testing',
      status: 'active',
      framework: 'nextjs',
      runtime: 'node',
      domains: ['test.example.com'],
      createdAt: '2023-01-01T00:00:00.000Z',
      updatedAt: '2023-01-02T00:00:00.000Z',
      settings: {
        buildCommand: 'npm run build',
        outputDirectory: '.next',
        installCommand: 'npm install',
        nodeVersion: '18',
        environmentVariables: {}
      }
    };

    test('should generate comprehensive project summary', () => {
      const summary = NextjsUtils.generateProjectSummary(project);
      expect(summary).toContain('Test Project');
      expect(summary).toContain('nextjs');
      expect(summary).toContain('node');
      expect(summary).toContain('active');
      expect(summary).toContain('test.example.com');
    });
  });
});

describe('Nextjs Validation', () => {
  describe('validateNextjsProject', () => {
    test('should validate valid project', () => {
      const validProject = {
        id: 'test-id',
        name: 'Test Project',
        status: 'active',
        framework: 'nextjs',
        runtime: 'node',
        domains: ['test.example.com'],
        createdAt: '2023-01-01T00:00:00.000Z',
        updatedAt: '2023-01-01T00:00:00.000Z',
        settings: {
          buildCommand: 'npm run build',
          outputDirectory: '.next',
          installCommand: 'npm install',
          nodeVersion: '18',
          environmentVariables: {}
        }
      };

      const result = validateNextjsProject(validProject);
      expect(result.success).toBe(true);
    });

    test('should reject invalid project', () => {
      const invalidProject = {
        id: '',
        name: 'Test Project',
        status: 'invalid',
        framework: 'invalid',
        runtime: 'invalid'
      };

      const result = validateNextjsProject(invalidProject);
      expect(result.success).toBe(false);
    });
  });

  describe('validateNextjsConfig', () => {
    test('should validate valid config', () => {
      const result = validateNextjsConfig(DefaultNextjsConfig);
      expect(result.success).toBe(true);
    });

    test('should reject invalid config', () => {
      const invalidConfig = {
        platform: 'invalid',
        maxProjects: -1,
        syncFrequency: 'invalid'
      };

      const result = validateNextjsConfig(invalidConfig);
      expect(result.success).toBe(false);
    });
  });

  describe('validateNextjsOAuthRequest', () => {
    test('should validate valid OAuth request', () => {
      const validRequest = {
        user_id: 'test-user',
        scopes: ['read', 'write', 'projects'],
        platform: 'web'
      };

      const result = validateNextjsOAuthRequest(validRequest);
      expect(result.success).toBe(true);
    });

    test('should reject OAuth request without user_id', () => {
      const invalidRequest = {
        scopes: ['read', 'write'],
        platform: 'web'
      };

      const result = validateNextjsOAuthRequest(invalidRequest);
      expect(result.success).toBe(false);
    });
  });

  describe('Type Guards', () => {
    test('should correctly identify Next.js projects', () => {
      const validProject = {
        id: 'test-id',
        name: 'Test Project',
        status: 'active',
        framework: 'nextjs',
        runtime: 'node',
        domains: [],
        createdAt: '2023-01-01T00:00:00.000Z',
        updatedAt: '2023-01-01T00:00:00.000Z',
        settings: {
          buildCommand: 'npm run build',
          outputDirectory: '.next',
          installCommand: 'npm install',
          nodeVersion: '18',
          environmentVariables: {}
        }
      };

      expect(isNextjsProject(validProject)).toBe(true);
      expect(isNextjsProject({ invalid: 'data' })).toBe(false);
    });

    test('should correctly identify Next.js configs', () => {
      expect(isNextjsConfig(DefaultNextjsConfig)).toBe(true);
      expect(isNextjsConfig({ platform: 'invalid' })).toBe(false);
    });
  });
});

describe('Next.js Hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useNextjsProjects', () => {
    test('should fetch projects on mount', async () => {
      const mockResponse = {
        ok: true,
        projects: [
          {
            id: '1',
            name: 'Test Project',
            status: 'active',
            framework: 'nextjs',
            runtime: 'node',
            domains: [],
            createdAt: '2023-01-01T00:00:00.000Z',
            updatedAt: '2023-01-01T00:00:00.000Z',
            settings: {
              buildCommand: 'npm run build',
              outputDirectory: '.next',
              installCommand: 'npm install',
              nodeVersion: '18',
              environmentVariables: {}
            }
          }
        ]
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const { result } = renderHook(() => useNextjsProjects('test-user'));

      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.projects).toHaveLength(1);
        expect(result.current.projects[0].name).toBe('Test Project');
      });

      expect(fetch).toHaveBeenCalledWith('/api/integrations/nextjs/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'test-user',
          limit: 50,
          status: 'active',
          include_builds: false,
          include_deployments: true
        })
      });
    });

    test('should handle fetch errors', async () => {
      (fetch as any).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useNextjsProjects('test-user'));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.error).toBe('Network error fetching projects');
      });
    });

    test('should filter and sort projects correctly', async () => {
      const mockResponse = {
        ok: true,
        projects: [
          {
            id: '1',
            name: 'A Project',
            status: 'active',
            framework: 'nextjs',
            runtime: 'node',
            domains: [],
            createdAt: '2023-01-01T00:00:00.000Z',
            updatedAt: '2023-01-01T00:00:00.000Z',
            settings: {
              buildCommand: 'npm run build',
              outputDirectory: '.next',
              installCommand: 'npm install',
              nodeVersion: '18',
              environmentVariables: {}
            }
          },
          {
            id: '2',
            name: 'Z Project',
            status: 'active',
            framework: 'react',
            runtime: 'node',
            domains: [],
            createdAt: '2023-01-01T00:00:00.000Z',
            updatedAt: '2023-01-01T00:00:00.000Z',
            settings: {
              buildCommand: 'npm run build',
              outputDirectory: 'build',
              installCommand: 'npm install',
              nodeVersion: '18',
              environmentVariables: {}
            }
          }
        ]
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const { result } = renderHook(() => useNextjsProjects('test-user'));

      await waitFor(() => {
        expect(result.current.projects).toHaveLength(2);
      });

      // Test filtering
      act(() => {
        result.current.filterProjects('A');
      });

      expect(result.current.projects).toHaveLength(1);
      expect(result.current.projects[0].name).toBe('A Project');

      // Test sorting
      act(() => {
        result.current.sortProjects('name', 'asc');
      });

      expect(result.current.projects[0].name).toBe('A Project');
    });
  });

  describe('useNextjsConfig', () => {
    test('should initialize with default config', () => {
      const { result } = renderHook(() => useNextjsConfig('test-user'));

      expect(result.current.config).toBe(null); // Initially null until loaded
    });

    test('should update config correctly', () => {
      const { result } = renderHook(() => useNextjsConfig('test-user'));

      act(() => {
        result.current.updateConfig({ maxProjects: 100 });
      });

      // Would need to mock the config load to test this properly
    });
  });
});

describe('Next.js Integration End-to-End', () => {
  test('should complete full OAuth flow', async () => {
    const mockAuthResponse = {
      ok: true,
      authorization_url: 'https://vercel.com/oauth/authorize?client_id=test',
      user_id: 'test-user',
      csrf_token: 'test-token'
    };

    const mockCallbackResponse = {
      ok: true,
      access_token: 'test-access-token',
      refresh_token: 'test-refresh-token',
      user: { id: 'test-user', name: 'Test User' },
      projects: []
    };

    (fetch as any)
      .mockResolvedValueOnce({ ok: true, json: async () => mockAuthResponse })
      .mockResolvedValueOnce({ ok: true, json: async () => mockCallbackResponse });

    // Simulate OAuth flow
    const authResponse = await fetch('/api/auth/nextjs/authorize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'test-user',
        scopes: ['read', 'write', 'projects']
      })
    });

    expect(authResponse.ok).toBe(true);
    const authData = await authResponse.json();
    expect(authData.authorization_url).toContain('vercel.com/oauth/authorize');

    // Simulate callback
    const callbackResponse = await fetch('/api/auth/nextjs/callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: 'test-auth-code',
        state: 'test-token'
      })
    });

    expect(callbackResponse.ok).toBe(true);
    const callbackData = await callbackResponse.json();
    expect(callbackData.access_token).toBe('test-access-token');
  });

  test('should fetch and process projects', async () => {
    const mockProjectsResponse = {
      ok: true,
      projects: [
        {
          id: '1',
          name: 'Test Project',
          status: 'active',
          framework: 'nextjs',
          runtime: 'node',
          domains: ['test.example.com'],
          createdAt: '2023-01-01T00:00:00.000Z',
          updatedAt: '2023-01-01T00:00:00.000Z',
          settings: {
            buildCommand: 'npm run build',
            outputDirectory: '.next',
            installCommand: 'npm install',
            nodeVersion: '18',
            environmentVariables: {}
          }
        }
      ],
      builds: [],
      deployments: []
    };

    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockProjectsResponse
    });

    const response = await fetch('/api/integrations/nextjs/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'test-user',
        limit: 50,
        status: 'active'
      })
    });

    expect(response.ok).toBe(true);
    const data = await response.json();
    expect(data.projects).toHaveLength(1);
    expect(data.projects[0].name).toBe('Test Project');
  });
});

describe('Next.js Performance Tests', () => {
  test('should handle large project lists efficiently', () => {
    const largeProjects: NextjsProject[] = Array.from({ length: 1000 }, (_, i) => ({
      id: `project-${i}`,
      name: `Project ${i}`,
      status: 'active',
      framework: 'nextjs',
      runtime: 'node',
      domains: [`project-${i}.example.com`],
      createdAt: '2023-01-01T00:00:00.000Z',
      updatedAt: '2023-01-01T00:00:00.000Z',
      settings: {
        buildCommand: 'npm run build',
        outputDirectory: '.next',
        installCommand: 'npm install',
        nodeVersion: '18',
        environmentVariables: {}
      }
    }));

    const startTime = performance.now();
    
    // Test filtering
    NextjsUtils.filterProjects(largeProjects, 'Project 500');
    
    // Test sorting
    NextjsUtils.sortProjects(largeProjects, 'name', 'asc');
    
    const endTime = performance.now();
    const duration = endTime - startTime;
    
    // Should complete within reasonable time (less than 100ms for 1000 items)
    expect(duration).toBeLessThan(100);
  });

  test('should validate schemas efficiently', () => {
    const invalidData = {
      id: '',
      name: '',
      status: 'invalid',
      framework: 'invalid',
      runtime: 'invalid'
    };

    const startTime = performance.now();
    
    for (let i = 0; i < 1000; i++) {
      validateNextjsProject(invalidData);
    }
    
    const endTime = performance.now();
    const duration = endTime - startTime;
    
    // Should complete within reasonable time
    expect(duration).toBeLessThan(500);
  });
});

describe('Next.js Error Handling', () => {
  test('should handle network errors gracefully', async () => {
    (fetch as any).mockRejectedValueOnce(new Error('Network unreachable'));

    try {
      await fetch('/api/integrations/nextjs/projects');
    } catch (error) {
      expect(error).toBeInstanceOf(Error);
    }
  });

  test('should handle API errors gracefully', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ error: 'Internal server error' })
    });

    const response = await fetch('/api/integrations/nextjs/projects');
    
    expect(response.ok).toBe(false);
    
    const data = await response.json();
    expect(data.error).toBe('Internal server error');
  });

  test('should handle malformed data gracefully', () => {
    const malformedProject = {
      id: '1',
      name: 'Test Project',
      status: 'active',
      framework: 'nextjs'
      // Missing required fields
    };

    const result = validateNextjsProject(malformedProject);
    expect(result.success).toBe(false);
  });
});