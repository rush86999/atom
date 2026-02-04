/**
 * GitLab Testing Suite
 * Comprehensive tests for GitLab integration
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider } from '@chakra-ui/react';
import { GitLabManager } from '../components/GitLabManager';
import { GitLabUtils } from '../utils';
import GitLabSkills from '../skills/gitlabSkills';
import { useGitLabProjects } from '../hooks';
import {
  GitLabProject,
  GitLabPipeline,
  GitLabIssue,
  GitLabMergeRequest
} from '../types';

// Mock fetch
global.fetch = jest.fn();

// Mock router
jest.mock('next/router', () => ({
  useRouter() {
    return {
      isReady: true,
      query: {},
      push: jest.fn(),
    };
  },
}));

// Test data
const mockGitLabProject: GitLabProject = {
  id: 123,
  name: 'Test Project',
  path: 'test-project',
  path_with_namespace: 'user/test-project',
  namespace: {
    id: 1,
    name: 'Test User',
    path: 'user',
    kind: 'user',
    full_path: 'user',
    web_url: 'https://gitlab.com/user'
  },
  visibility: 'private',
  archived: false,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T12:00:00Z',
  last_activity_at: '2023-01-01T12:00:00Z',
  star_count: 10,
  forks_count: 5,
  open_issues_count: 3,
  runners_token: 'token123',
  public_jobs: true,
  shared_with_groups: [],
  only_allow_merge_if_pipeline_succeeds: false,
  allow_merge_on_skipped_pipeline: false,
  remove_source_branch_after_merge: false,
  printing_merge_request_link_enabled: true,
  lfs_enabled: true,
  request_access_enabled: true,
  merge_method: 'merge',
  auto_devops_enabled: false,
  build_coverage_regex: '',
  ci_config_path: '',
  shared_runners_enabled: true,
  runners_enabled: true,
  wiki_access_level: 'enabled',
  snippets_access_level: 'enabled',
  issues_access_level: 'enabled',
  repository_access_level: 'enabled',
  merge_requests_access_level: 'enabled',
  forking_access_level: 'enabled',
  builds_access_level: 'enabled',
  packages_enabled: true,
  service_desk_enabled: false,
  autoclose_referenced_issues: true,
  enforce_auth_checks_on_uploads: false,
  container_registry_enabled: true,
  container_registry_access_level: 'enabled',
  security_and_compliance_enabled: false
};

const mockGitLabPipeline: GitLabPipeline = {
  id: 456,
  iid: 1,
  project_id: 123,
  sha: 'abc123',
  ref: 'main',
  status: 'success',
  source: 'push',
  created_at: '2023-01-01T10:00:00Z',
  updated_at: '2023-01-01T10:05:00Z',
  started_at: '2023-01-01T10:01:00Z',
  finished_at: '2023-01-01T10:05:00Z',
  duration: 240,
  coverage: '85.5',
  web_url: 'https://gitlab.com/user/test-project/-/pipelines/1',
  jobs: [],
  variables: []
};

const mockGitLabIssue: GitLabIssue = {
  id: 789,
  iid: 1,
  project_id: 123,
  title: 'Test Issue',
  description: 'This is a test issue',
  state: 'opened',
  created_at: '2023-01-01T09:00:00Z',
  updated_at: '2023-01-01T09:30:00Z',
  author: {
    id: 1,
    name: 'Test User',
    username: 'testuser',
    state: 'active',
    avatar_url: 'https://gitlab.com/avatar.png',
    web_url: 'https://gitlab.com/testuser'
  },
  assignees: [],
  labels: [],
  notes: [],
  updated_by_id: 1,
  confidential: false,
  discussion_locked: false,
  web_url: 'https://gitlab.com/user/test-project/-/issues/1',
  time_stats: {
    time_estimate: 0,
    total_time_spent: 0,
    human_time_estimate: '',
    human_total_time_spent: ''
  }
};

const mockGitLabMergeRequest: GitLabMergeRequest = {
  id: 1011,
  iid: 1,
  project_id: 123,
  title: 'Test Merge Request',
  description: 'This is a test merge request',
  state: 'opened',
  created_at: '2023-01-01T08:00:00Z',
  updated_at: '2023-01-01T08:30:00Z',
  author: {
    id: 1,
    name: 'Test User',
    username: 'testuser',
    state: 'active',
    avatar_url: 'https://gitlab.com/avatar.png',
    web_url: 'https://gitlab.com/testuser'
  },
  assignees: [],
  reviewers: [],
  source_branch: 'feature-branch',
  source_project_id: 123,
  target_branch: 'main',
  target_project_id: 123,
  labels: [],
  milestone: undefined,
  draft: false,
  work_in_progress: false,
  merge_when_pipeline_succeeds: false,
  merge_status: 'can_be_merged',
  sha: 'def456',
  discussions_locked: false,
  should_remove_source_branch: false,
  force_remove_source_branch: false,
  reference: '!1',
  references: {
    short: '!1',
    relative: '!1',
    full: 'user/test-project!1'
  },
  web_url: 'https://gitlab.com/user/test-project/-/merge_requests/1'
};

// Helper component for testing
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <ChakraProvider>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ChakraProvider>
  );
};

describe('GitLab Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (fetch as jest.Mock).mockReset();
  });

  describe('GitLabManager Component', () => {
    it('renders GitLab integration interface', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            status: 'healthy',
            connected: false
          })
        })
      );

      render(
        <TestWrapper>
          <GitLabManager userId="test-user" />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('GitLab Integration')).toBeInTheDocument();
        expect(screen.getByText('Manage your GitLab repositories and workflows')).toBeInTheDocument();
      });
    });

    it('shows connection status', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            status: 'healthy',
            connected: true
          })
        })
      );

      render(
        <TestWrapper>
          <GitLabManager userId="test-user" />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('GitLab Connection')).toBeInTheDocument();
        expect(screen.getByText('Successfully connected to GitLab API')).toBeInTheDocument();
      });
    });

    it('handles OAuth connection', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            authorization_url: 'https://gitlab.com/oauth/authorize?response_type=code&client_id=test'
          })
        })
      );

      render(
        <TestWrapper>
          <GitLabManager userId="test-user" />
        </TestWrapper>
      );

      const connectButton = screen.getByText('Connect GitLab');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/integrations/gitlab/authorize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('user_id=test-user')
        });
      });
    });
  });

  describe('GitLab Utils', () => {
    it('formats commit SHA correctly', () => {
      const longSha = 'abcdefghijklmnopqrstuvwxyz123456';
      const shortSha = GitLabUtils.formatCommitSha(longSha);
      expect(shortSha).toBe('abcd1234');
    });

    it('formats duration correctly', () => {
      expect(GitLabUtils.formatDuration(30)).toBe('30s');
      expect(GitLabUtils.formatDuration(90)).toBe('1m 30s');
      expect(GitLabUtils.formatDuration(3660)).toBe('1h 1m');
      expect(GitLabUtils.formatDuration(undefined)).toBe('N/A');
    });

    it('gets relative time correctly', () => {
      const now = new Date();
      const oneMinuteAgo = new Date(now.getTime() - 60000);
      const oneHourAgo = new Date(now.getTime() - 3600000);
      
      expect(GitLabUtils.getRelativeTime(oneMinuteAgo.toISOString())).toBe('1m ago');
      expect(GitLabUtils.getRelativeTime(oneHourAgo.toISOString())).toBe('1h ago');
      expect(GitLabUtils.getRelativeTime(now.toISOString())).toBe('just now');
    });

    it('filters projects correctly', () => {
      const projects = [
        { ...mockGitLabProject, name: 'Test Project 1' },
        { ...mockGitLabProject, name: 'Another Project' },
        { ...mockGitLabProject, name: 'Test Project 2' }
      ];

      const filtered = GitLabUtils.filterProjects(projects, 'test');
      expect(filtered).toHaveLength(2);
      expect(filtered[0].name).toBe('Test Project 1');
      expect(filtered[1].name).toBe('Test Project 2');
    });

    it('sorts projects correctly', () => {
      const projects = [
        { ...mockGitLabProject, name: 'Z Project' },
        { ...mockGitLabProject, name: 'A Project' },
        { ...mockGitLabProject, name: 'M Project' }
      ];

      const sorted = GitLabUtils.sortProjects(projects, 'name', 'asc');
      expect(sorted[0].name).toBe('A Project');
      expect(sorted[1].name).toBe('M Project');
      expect(sorted[2].name).toBe('Z Project');
    });

    it('gets pipeline status color correctly', () => {
      expect(GitLabUtils.getPipelineStatusColor('success')).toBe('green');
      expect(GitLabUtils.getPipelineStatusColor('failed')).toBe('red');
      expect(GitLabUtils.getPipelineStatusColor('running')).toBe('blue');
      expect(GitLabUtils.getPipelineStatusColor('unknown')).toBe('gray');
    });

    it('gets project visibility color correctly', () => {
      expect(GitLabUtils.getProjectVisibilityColor('public')).toBe('green');
      expect(GitLabUtils.getProjectVisibilityColor('private')).toBe('red');
      expect(GitLabUtils.getProjectVisibilityColor('internal')).toBe('yellow');
    });

    it('calculates pipeline success rate correctly', () => {
      const pipelines = [
        { ...mockGitLabPipeline, status: 'success' },
        { ...mockGitLabPipeline, status: 'success' },
        { ...mockGitLabPipeline, status: 'failed' },
        { ...mockGitLabPipeline, status: 'running' }
      ];

      const successRate = GitLabUtils.calculatePipelineSuccessRate(pipelines);
      expect(successRate).toBe(50); // 2 out of 4
    });

    it('generates project summary correctly', () => {
      const summary = GitLabUtils.generateProjectSummary(mockGitLabProject);
      expect(summary).toContain('Test Project');
      expect(summary).toContain('private');
      expect(summary).toContain('10 Stars');
      expect(summary).toContain('5 Forks');
    });
  });

  describe('GitLab Skills', () => {
    beforeEach(() => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            data: { projects: [] }
          })
        })
      );
    });

    it('lists GitLab projects successfully', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            data: {
              projects: [mockGitLabProject],
              stats: {
                total: 1,
                private: 1,
                public: 0,
                internal: 0,
                archived: 0
              }
            }
          })
        })
      );

      const result = await GitLabSkills['gitlab-list-projects']({
        user_id: 'test-user',
        limit: 50
      });

      expect(result.success).toBe(true);
      expect(result.data?.projects).toHaveLength(1);
      expect(result.data?.stats.total).toBe(1);
    });

    it('gets GitLab project details successfully', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            data: {
              project: mockGitLabProject,
              pipelines: [mockGitLabPipeline],
              issues: [mockGitLabIssue],
              merge_requests: [mockGitLabMergeRequest]
            }
          })
        })
      );

      const result = await GitLabSkills['gitlab-get-project']({
        user_id: 'test-user',
        project_id: 123
      });

      expect(result.success).toBe(true);
      expect(result.data?.project.id).toBe(123);
      expect(result.data?.pipelines).toHaveLength(1);
      expect(result.data?.issues).toHaveLength(1);
      expect(result.data?.merge_requests).toHaveLength(1);
    });

    it('creates GitLab issue successfully', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            data: {
              issue: { ...mockGitLabIssue, title: 'New Issue' },
              url: 'https://gitlab.com/user/test-project/-/issues/2'
            }
          })
        })
      );

      const result = await GitLabSkills['gitlab-create-issue']({
        user_id: 'test-user',
        project_id: 123,
        title: 'New Issue',
        description: 'This is a new issue',
        labels: ['bug', 'high-priority']
      });

      expect(result.success).toBe(true);
      expect(result.data?.issue.title).toBe('New Issue');
      expect(result.data?.url).toContain('/issues/2');
    });

    it('triggers GitLab pipeline successfully', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            data: {
              pipeline: { ...mockGitLabPipeline, id: 457 },
              url: 'https://gitlab.com/user/test-project/-/pipelines/2'
            }
          })
        })
      );

      const result = await GitLabSkills['gitlab-trigger-pipeline']({
        user_id: 'test-user',
        project_id: 123,
        ref: 'main'
      });

      expect(result.success).toBe(true);
      expect(result.data?.pipeline.id).toBe(457);
      expect(result.data?.status).toBe('success');
    });

    it('handles API errors correctly', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: false,
          json: () => Promise.resolve({
            error: 'API Error'
          })
        })
      );

      const result = await GitLabSkills['gitlab-list-projects']({
        user_id: 'test-user'
      });

      expect(result.success).toBe(false);
      expect(result.error).toBe('API Error');
    });
  });

  describe('GitLab Hooks', () => {
    it('fetches projects successfully', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            projects: [mockGitLabProject]
          })
        })
      );

      const { result } = useGitLabProjects('test-user', { limit: 10 });

      expect(result.current.loading).toBe(false);
      expect(result.current.projects).toHaveLength(0); // Initial state
    });

    it('handles loading state', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        new Promise(resolve => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: () => Promise.resolve({
                ok: true,
                projects: [mockGitLabProject]
              })
            });
          }, 1000);
        })
      );

      const { result } = useGitLabProjects('test-user');

      expect(result.current.loading).toBe(true);
    });

    it('handles error state', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      const { result } = useGitLabProjects('test-user');

      // Wait for error to propagate
      await waitFor(() => {
        expect(result.current.error).not.toBeNull();
      });
    });
  });

  describe('GitLab Types', () => {
    it('validates GitLabProject type structure', () => {
      const project: GitLabProject = mockGitLabProject;
      
      expect(project.id).toBe(123);
      expect(project.name).toBe('Test Project');
      expect(project.visibility).toBe('private');
      expect(project.namespace.name).toBe('Test User');
      expect(Array.isArray(project.shared_with_groups)).toBe(true);
    });

    it('validates GitLabPipeline type structure', () => {
      const pipeline: GitLabPipeline = mockGitLabPipeline;
      
      expect(pipeline.id).toBe(456);
      expect(pipeline.project_id).toBe(123);
      expect(pipeline.status).toBe('success');
      expect(pipeline.duration).toBe(240);
      expect(Array.isArray(pipeline.jobs)).toBe(true);
    });

    it('validates GitLabIssue type structure', () => {
      const issue: GitLabIssue = mockGitLabIssue;
      
      expect(issue.id).toBe(789);
      expect(issue.project_id).toBe(123);
      expect(issue.state).toBe('opened');
      expect(issue.author.name).toBe('Test User');
      expect(Array.isArray(issue.labels)).toBe(true);
    });

    it('validates GitLabMergeRequest type structure', () => {
      const mr: GitLabMergeRequest = mockGitLabMergeRequest;
      
      expect(mr.id).toBe(1011);
      expect(mr.project_id).toBe(123);
      expect(mr.state).toBe('opened');
      expect(mr.source_branch).toBe('feature-branch');
      expect(mr.target_branch).toBe('main');
      expect(mr.merge_status).toBe('can_be_merged');
    });
  });

  describe('GitLab Integration Integration', () => {
    it('handles full workflow from connection to data retrieval', async () => {
      const mockFetch = fetch as jest.Mock;
      
      // Mock health check
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            status: 'healthy',
            connected: false
          })
        })
      );

      // Mock OAuth initiation
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            authorization_url: 'https://gitlab.com/oauth/authorize'
          })
        })
      );

      // Mock projects fetch
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            projects: [mockGitLabProject],
            pipelines: [mockGitLabPipeline],
            issues: [mockGitLabIssue],
            merge_requests: [mockGitLabMergeRequest]
          })
        })
      );

      render(
        <TestWrapper>
          <GitLabManager userId="test-user" />
        </TestWrapper>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText('GitLab Integration')).toBeInTheDocument();
      });

      // Click connect button
      const connectButton = screen.getByText('Connect GitLab');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/integrations/gitlab/authorize', expect.any(Object));
      });
    });

    it('handles project selection and details view', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            data: { project: mockGitLabProject }
          })
        })
      );

      render(
        <TestWrapper>
          <GitLabManager userId="test-user" />
        </TestWrapper>
      );

      // Switch to projects tab
      const projectsTab = screen.getByText('Projects');
      fireEvent.click(projectsTab);

      await waitFor(() => {
        expect(screen.getByText('GitLab Projects')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('handles network errors gracefully', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      render(
        <TestWrapper>
          <GitLabManager userId="test-user" />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Network error/)).toBeInTheDocument();
      });
    });

    it('handles API error responses', async () => {
      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({
            error: 'Unauthorized'
          })
        })
      );

      render(
        <TestWrapper>
          <GitLabManager userId="test-user" />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Unauthorized/)).toBeInTheDocument();
      });
    });

    it('handles missing required parameters', async () => {
      const result = await GitLabSkills['gitlab-list-projects']({
        // Missing user_id
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('required');
    });
  });

  describe('Performance', () => {
    it('handles large number of projects efficiently', async () => {
      const manyProjects = Array.from({ length: 100 }, (_, i) => ({
        ...mockGitLabProject,
        id: i,
        name: `Project ${i}`
      }));

      const mockFetch = fetch as jest.Mock;
      mockFetch.mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ok: true,
            projects: manyProjects
          })
        })
      );

      const startTime = performance.now();
      
      const result = await GitLabSkills['gitlab-list-projects']({
        user_id: 'test-user',
        limit: 100
      });
      
      const endTime = performance.now();
      
      expect(result.success).toBe(true);
      expect(result.data?.projects).toHaveLength(100);
      expect(endTime - startTime).toBeLessThan(1000); // Should complete within 1 second
    });

    it('filters and sorts efficiently', () => {
      const manyProjects = Array.from({ length: 1000 }, (_, i) => ({
        ...mockGitLabProject,
        id: i,
        name: `Project ${i}`,
        star_count: Math.floor(Math.random() * 100)
      }));

      const startTime = performance.now();
      
      const filtered = GitLabUtils.filterProjects(manyProjects, 'Project 1');
      const sorted = GitLabUtils.sortProjects(filtered, 'star_count', 'desc');
      
      const endTime = performance.now();
      
      expect(sorted.length).toBeGreaterThan(0);
      expect(endTime - startTime).toBeLessThan(100); // Should complete within 100ms
    });
  });
});

export default GitLabIntegrationTests;