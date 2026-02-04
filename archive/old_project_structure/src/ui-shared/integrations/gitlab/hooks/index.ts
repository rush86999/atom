/**
 * GitLab Integration Hooks
 * Custom React hooks for GitLab data management
 */

import { useState, useEffect, useCallback } from 'react';
import { toast } from '@chakra-ui/react';
import {
  GitLabProject,
  GitLabPipeline,
  GitLabIssue,
  GitLabMergeRequest,
  GitLabConfig,
  GitLabUser,
  GitLabGroup
} from '../types';

interface UseGitLabProjectsOptions {
  limit?: number;
  visibility?: 'all' | 'public' | 'private' | 'internal';
  archived?: boolean;
  includePipelines?: boolean;
  includeIssues?: boolean;
  includeMergeRequests?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseGitLabProjectsReturn {
  projects: GitLabProject[];
  pipelines: GitLabPipeline[];
  issues: GitLabIssue[];
  mergeRequests: GitLabMergeRequest[];
  loading: boolean;
  error: string | null;
  refreshProjects: () => Promise<void>;
  filterProjects: (searchTerm: string) => void;
  sortProjects: (sortBy: string, sortOrder?: 'asc' | 'desc') => void;
  projectStats: {
    total: number;
    active: number;
    archived: number;
    public: number;
    private: number;
    internal: number;
  };
}

export const useGitLabProjects = (
  userId: string,
  options: UseGitLabProjectsOptions = {}
): UseGitLabProjectsReturn => {
  const {
    limit = 50,
    visibility = 'all',
    archived = false,
    includePipelines = true,
    includeIssues = true,
    includeMergeRequests = true,
    autoRefresh = false,
    refreshInterval = 300000 // 5 minutes
  } = options;

  const [projects, setProjects] = useState<GitLabProject[]>([]);
  const [pipelines, setPipelines] = useState<GitLabPipeline[]>([]);
  const [issues, setIssues] = useState<GitLabIssue[]>([]);
  const [mergeRequests, setMergeRequests] = useState<GitLabMergeRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('updated_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const fetchProjects = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/integrations/gitlab/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit,
          visibility,
          archived,
          include_pipelines: includePipelines,
          include_issues: includeIssues,
          include_merge_requests: includeMergeRequests
        })
      });

      const data = await response.json();

      if (data.ok) {
        setProjects(data.projects || []);
        setPipelines(data.pipelines || []);
        setIssues(data.issues || []);
        setMergeRequests(data.merge_requests || []);
      } else {
        setError(data.error || 'Failed to fetch GitLab projects');
      }
    } catch (err) {
      setError('Network error fetching GitLab projects');
      console.error('GitLab projects fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [userId, limit, visibility, archived, includePipelines, includeIssues, includeMergeRequests]);

  const refreshProjects = useCallback(async () => {
    await fetchProjects();
    toast({
      title: 'Projects Refreshed',
      description: 'GitLab projects have been updated',
      status: 'success',
      duration: 2000,
    });
  }, [fetchProjects]);

  const filterProjects = useCallback((term: string) => {
    setSearchTerm(term);
  }, []);

  const sortProjects = useCallback((newSortBy: string, newOrder: 'asc' | 'desc' = 'desc') => {
    setSortBy(newSortBy);
    setSortOrder(newOrder);
  }, []);

  const projectStats = {
    total: projects.length,
    active: projects.filter(p => !p.archived).length,
    archived: projects.filter(p => p.archived).length,
    public: projects.filter(p => p.visibility === 'public').length,
    private: projects.filter(p => p.visibility === 'private').length,
    internal: projects.filter(p => p.visibility === 'internal').length
  };

  // Apply filtering and sorting
  const processedProjects = GitLabUtils.sortProjects(
    GitLabUtils.filterProjects(projects, searchTerm),
    sortBy,
    sortOrder
  );

  // Update projects with processed ones
  useEffect(() => {
    setProjects(processedProjects);
  }, [processedProjects]);

  // Initial load
  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Auto refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchProjects();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchProjects]);

  return {
    projects,
    pipelines,
    issues,
    mergeRequests,
    loading,
    error,
    refreshProjects,
    filterProjects,
    sortProjects,
    projectStats
  };
};

interface UseGitLabPipelinesOptions {
  limit?: number;
  projectId?: number;
  status?: string;
  ref?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseGitLabPipelinesReturn {
  pipelines: GitLabPipeline[];
  loading: boolean;
  error: string | null;
  refreshPipelines: () => Promise<void>;
  pipelineStats: {
    total: number;
    success: number;
    failed: number;
    running: number;
    pending: number;
  };
}

export const useGitLabPipelines = (
  userId: string,
  options: UseGitLabPipelinesOptions = {}
): UseGitLabPipelinesReturn => {
  const {
    limit = 100,
    projectId,
    status,
    ref,
    autoRefresh = false,
    refreshInterval = 300000 // 5 minutes
  } = options;

  const [pipelines, setPipelines] = useState<GitLabPipeline[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPipelines = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/integrations/gitlab/pipelines', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit,
          project_id: projectId,
          status,
          ref,
          include_jobs: true
        })
      });

      const data = await response.json();

      if (data.ok) {
        setPipelines(data.pipelines || []);
      } else {
        setError(data.error || 'Failed to fetch GitLab pipelines');
      }
    } catch (err) {
      setError('Network error fetching GitLab pipelines');
      console.error('GitLab pipelines fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [userId, limit, projectId, status, ref]);

  const refreshPipelines = useCallback(async () => {
    await fetchPipelines();
    toast({
      title: 'Pipelines Refreshed',
      description: 'GitLab pipelines have been updated',
      status: 'success',
      duration: 2000,
    });
  }, [fetchPipelines]);

  const pipelineStats = {
    total: pipelines.length,
    success: pipelines.filter(p => p.status === 'success').length,
    failed: pipelines.filter(p => p.status === 'failed').length,
    running: pipelines.filter(p => p.status === 'running').length,
    pending: pipelines.filter(p => p.status === 'pending').length
  };

  // Initial load
  useEffect(() => {
    fetchPipelines();
  }, [fetchPipelines]);

  // Auto refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchPipelines();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchPipelines]);

  return {
    pipelines,
    loading,
    error,
    refreshPipelines,
    pipelineStats
  };
};

interface UseGitLabIssuesOptions {
  limit?: number;
  projectId?: number;
  state?: string;
  labels?: string[];
  milestone?: string;
  author?: string;
  assignee?: string;
}

interface UseGitLabIssuesReturn {
  issues: GitLabIssue[];
  loading: boolean;
  error: string | null;
  refreshIssues: () => Promise<void>;
  issueStats: {
    total: number;
    opened: number;
    closed: number;
    confidential: number;
    weighted: number;
  };
}

export const useGitLabIssues = (
  userId: string,
  options: UseGitLabIssuesOptions = {}
): UseGitLabIssuesReturn => {
  const {
    limit = 100,
    projectId,
    state = 'opened',
    labels,
    milestone,
    author,
    assignee
  } = options;

  const [issues, setIssues] = useState<GitLabIssue[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchIssues = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/integrations/gitlab/issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit,
          project_id: projectId,
          state,
          labels,
          milestone,
          author,
          assignee
        })
      });

      const data = await response.json();

      if (data.ok) {
        setIssues(data.issues || []);
      } else {
        setError(data.error || 'Failed to fetch GitLab issues');
      }
    } catch (err) {
      setError('Network error fetching GitLab issues');
      console.error('GitLab issues fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [userId, limit, projectId, state, labels, milestone, author, assignee]);

  const refreshIssues = useCallback(async () => {
    await fetchIssues();
    toast({
      title: 'Issues Refreshed',
      description: 'GitLab issues have been updated',
      status: 'success',
      duration: 2000,
    });
  }, [fetchIssues]);

  const issueStats = {
    total: issues.length,
    opened: issues.filter(i => i.state === 'opened').length,
    closed: issues.filter(i => i.state === 'closed').length,
    confidential: issues.filter(i => i.confidential).length,
    weighted: issues.filter(i => i.weight !== undefined).length
  };

  // Initial load
  useEffect(() => {
    fetchIssues();
  }, [fetchIssues]);

  return {
    issues,
    loading,
    error,
    refreshIssues,
    issueStats
  };
};

interface UseGitLabConfigReturn {
  config: GitLabConfig | null;
  updateConfig: (updates: Partial<GitLabConfig>) => void;
  saveConfig: () => Promise<void>;
  resetConfig: () => void;
  loading: boolean;
  error: string | null;
}

export const useGitLabConfig = (userId: string): UseGitLabConfigReturn => {
  const [config, setConfig] = useState<GitLabConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateConfig = useCallback((updates: Partial<GitLabConfig>) => {
    if (!config) return;

    const newConfig = { ...config, ...updates };
    setConfig(newConfig);
  }, [config]);

  const saveConfig = useCallback(async () => {
    if (!config || !userId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/integrations/gitlab/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          config
        })
      });

      const data = await response.json();

      if (data.ok) {
        toast({
          title: 'Configuration Saved',
          description: 'GitLab integration settings have been saved',
          status: 'success',
          duration: 2000,
        });
      } else {
        throw new Error(data.error || 'Failed to save configuration');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Save failed';
      setError(errorMessage);

      toast({
        title: 'Save Failed',
        description: errorMessage,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [config, userId]);

  const resetConfig = useCallback(() => {
    // Reset to default configuration
    setConfig({
      platform: 'gitlab',
      projects: [],
      groups: [],
      include_private_projects: true,
      include_internal_projects: true,
      include_public_projects: false,
      sync_frequency: 'realtime',
      include_pipelines: true,
      include_jobs: true,
      include_issues: true,
      include_merge_requests: true,
      include_releases: true,
      include_webhooks: true,
      max_projects: 50,
      max_pipelines: 100,
      max_jobs: 200,
      max_issues: 100,
      max_merge_requests: 100,
      date_range: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
        end: new Date()
      },
      webhook_events: [
        'push',
        'merge_request',
        'issue',
        'pipeline',
        'job'
      ],
      enable_notifications: true,
      background_sync: true,
    });
  }, []);

  return {
    config,
    updateConfig,
    saveConfig,
    resetConfig,
    loading,
    error
  };
};

// Hook for real-time updates via webhooks
export const useGitLabWebhooks = (userId: string, projectIds: number[] = []) => {
  const [updates, setUpdates] = useState<any[]>([]);

  useEffect(() => {
    if (!userId || projectIds.length === 0) return;

    // Setup WebSocket connection for real-time updates
    const ws = new WebSocket(`${process.env.NEXT_PUBLIC_WS_URL}/gitlab/webhooks`);

    ws.onopen = () => {
      // Subscribe to project updates
      ws.send(JSON.stringify({
        type: 'subscribe',
        user_id: userId,
        project_ids: projectIds
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'update') {
        setUpdates(prev => [data.payload, ...prev].slice(0, 50)); // Keep last 50 updates
        
        // Show toast for important events
        if (['merge_request', 'issue', 'pipeline', 'job'].includes(data.event)) {
          const status = data.event.includes('failed') ? 'error' : 'success';
          toast({
            title: `GitLab ${data.event}`,
            description: data.payload.project_name || 'Project update',
            status: status as any,
            duration: 5000,
          });
        }
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return () => {
      ws.close();
    };
  }, [userId, projectIds]);

  return updates;
};

// Hook for GitLab health monitoring
export const useGitLabHealth = (userId: string) => {
  const [health, setHealth] = useState({
    connected: false,
    status: 'unknown',
    user: null as GitLabUser | null,
    token_status: 'unknown',
    last_check: null,
    error: null
  });

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations/gitlab/health', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
      });

      const data = await response.json();
      
      if (response.ok) {
        setHealth({
          connected: data.connected,
          status: data.status,
          user: data.user,
          token_status: data.token_status,
          last_check: data.last_check,
          error: null
        });
      } else {
        setHealth(prev => ({
          ...prev,
          connected: false,
          error: data.error || 'Health check failed'
        }));
      }
    } catch (err) {
      setHealth(prev => ({
        ...prev,
        connected: false,
        error: 'Health check error'
      }));
    }
  }, [userId]);

  useEffect(() => {
    checkHealth();
    
    // Check health every 2 minutes
    const interval = setInterval(checkHealth, 120000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return {
    health,
    checkHealth
  };
};