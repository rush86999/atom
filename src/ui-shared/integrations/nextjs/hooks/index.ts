/**
 * Next.js Integration Hooks
 * Custom React hooks for Next.js/Vercel integration
 */

import { useState, useEffect, useCallback } from 'react';
import { toast } from '@chakra-ui/react';
import { 
  NextjsProject, 
  NextjsBuild, 
  NextjsDeployment, 
  NextjsAnalytics,
  NextjsConfig 
} from '../types';
import { NextjsUtils } from '../utils';

interface UseNextjsProjectsOptions {
  limit?: number;
  status?: string;
  includeBuilds?: boolean;
  includeDeployments?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseNextjsProjectsReturn {
  projects: NextjsProject[];
  builds: NextjsBuild[];
  deployments: NextjsDeployment[];
  loading: boolean;
  error: string | null;
  refreshProjects: () => Promise<void>;
  filterProjects: (searchTerm: string) => void;
  sortProjects: (sortBy: string, order?: 'asc' | 'desc') => void;
  projectStats: {
    total: number;
    active: number;
    building: number;
    error: number;
    successRate: number;
  };
}

export const useNextjsProjects = (
  userId: string,
  options: UseNextjsProjectsOptions = {}
): UseNextjsProjectsReturn => {
  const {
    limit = 50,
    status = 'active',
    includeBuilds = false,
    includeDeployments = true,
    autoRefresh = false,
    refreshInterval = 60000
  } = options;

  const [projects, setProjects] = useState<NextjsProject[]>([]);
  const [builds, setBuilds] = useState<NextjsBuild[]>([]);
  const [deployments, setDeployments] = useState<NextjsDeployment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('updatedAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const fetchProjects = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/integrations/nextjs/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit,
          status,
          include_builds: includeBuilds,
          include_deployments: includeDeployments
        })
      });

      const data = await response.json();

      if (data.ok) {
        setProjects(data.projects || []);
        if (includeBuilds) setBuilds(data.builds || []);
        if (includeDeployments) setDeployments(data.deployments || []);
      } else {
        setError(data.error || 'Failed to fetch projects');
      }
    } catch (err) {
      setError('Network error fetching projects');
      console.error('Next.js projects fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [userId, limit, status, includeBuilds, includeDeployments]);

  const refreshProjects = useCallback(async () => {
    await fetchProjects();
    toast({
      title: 'Projects Refreshed',
      description: 'Next.js projects have been updated',
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

  // Calculate project statistics
  const projectStats = {
    total: projects.length,
    active: projects.filter(p => p.status === 'active').length,
    building: projects.filter(p => p.status === 'building').length,
    error: projects.filter(p => p.status === 'error').length,
    successRate: builds.length > 0 ? NextjsUtils.calculateBuildSuccessRate(builds) : 0
  };

  // Apply filtering and sorting
  const processedProjects = NextjsUtils.sortProjects(
    NextjsUtils.filterProjects(projects, searchTerm),
    sortBy,
    sortOrder
  );

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
    projects: processedProjects,
    builds,
    deployments,
    loading,
    error,
    refreshProjects,
    filterProjects,
    sortProjects,
    projectStats
  };
};

interface UseNextjsAnalyticsOptions {
  projectId: string;
  dateRange?: {
    start: string;
    end: string;
  };
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseNextjsAnalyticsReturn {
  analytics: NextjsAnalytics | null;
  loading: boolean;
  error: string | null;
  refreshAnalytics: () => Promise<void>;
  performanceGrade: 'A' | 'B' | 'C' | 'D' | 'F';
  metrics: {
    pageViews: number;
    uniqueVisitors: number;
    bounceRate: number;
    avgLoadTime: number;
    errorRate: number;
  };
}

export const useNextjsAnalytics = (
  userId: string,
  options: UseNextjsAnalyticsOptions
): UseNextjsAnalyticsReturn => {
  const { projectId, dateRange, autoRefresh = false, refreshInterval = 300000 } = options;

  const [analytics, setAnalytics] = useState<NextjsAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = useCallback(async () => {
    if (!userId || !projectId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/integrations/nextjs/analytics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          project_id: projectId,
          date_range: dateRange || {
            start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
            end: new Date().toISOString()
          }
        })
      });

      const data = await response.json();

      if (data.ok) {
        setAnalytics(data.analytics);
      } else {
        setError(data.error || 'Failed to fetch analytics');
      }
    } catch (err) {
      setError('Network error fetching analytics');
      console.error('Next.js analytics fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [userId, projectId, dateRange]);

  const refreshAnalytics = useCallback(async () => {
    await fetchAnalytics();
    toast({
      title: 'Analytics Refreshed',
      description: 'Analytics data has been updated',
      status: 'success',
      duration: 2000,
    });
  }, [fetchAnalytics]);

  // Calculate derived metrics
  const metrics = analytics ? {
    pageViews: analytics.metrics.pageViews,
    uniqueVisitors: analytics.metrics.uniqueVisitors,
    bounceRate: analytics.metrics.bounceRate,
    avgLoadTime: analytics.metrics.performance.avgLoadTime,
    errorRate: analytics.metrics.performance.errors / analytics.metrics.pageViews * 100
  } : {
    pageViews: 0,
    uniqueVisitors: 0,
    bounceRate: 0,
    avgLoadTime: 0,
    errorRate: 0
  };

  const performanceGrade = analytics ? 
    NextjsUtils.getPerformanceGrade(analytics.metrics) : 'F';

  // Initial load
  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // Auto refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchAnalytics();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchAnalytics]);

  return {
    analytics,
    loading,
    error,
    refreshAnalytics,
    performanceGrade,
    metrics
  };
};

interface UseNextjsDeploymentOptions {
  projectId: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseNextjsDeploymentReturn {
  triggerDeployment: (branch?: string) => Promise<void>;
  loading: boolean;
  error: string | null;
  deploymentStatus: {
    status: string;
    url?: string;
    progress: number;
  };
}

export const useNextjsDeployment = (
  userId: string,
  options: UseNextjsDeploymentOptions
): UseNextjsDeploymentReturn => {
  const { projectId, autoRefresh = false, refreshInterval = 30000 } = options;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deploymentStatus, setDeploymentStatus] = useState({
    status: 'idle',
    url: undefined as string | undefined,
    progress: 0
  });

  const triggerDeployment = useCallback(async (branch = 'main') => {
    if (!userId || !projectId) return;

    setLoading(true);
    setError(null);
    setDeploymentStatus({ status: 'triggering', url: undefined, progress: 0 });

    try {
      const response = await fetch('/api/integrations/nextjs/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          project_id: projectId,
          branch
        })
      });

      const data = await response.json();

      if (data.ok) {
        setDeploymentStatus({
          status: 'triggered',
          url: data.deployment?.url,
          progress: 100
        });

        toast({
          title: 'Deployment Triggered',
          description: `Deployment for branch "${branch}" has been started`,
          status: 'success',
          duration: 3000,
        });
      } else {
        throw new Error(data.error || 'Failed to trigger deployment');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Deployment failed';
      setError(errorMessage);
      setDeploymentStatus({ status: 'error', url: undefined, progress: 0 });

      toast({
        title: 'Deployment Failed',
        description: errorMessage,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [userId, projectId]);

  return {
    triggerDeployment,
    loading,
    error,
    deploymentStatus
  };
};

interface UseNextjsConfigReturn {
  config: NextjsConfig | null;
  updateConfig: (updates: Partial<NextjsConfig>) => void;
  saveConfig: () => Promise<void>;
  resetConfig: () => void;
  loading: boolean;
  error: string | null;
}

export const useNextjsConfig = (userId: string): UseNextjsConfigReturn => {
  const [config, setConfig] = useState<NextjsConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateConfig = useCallback((updates: Partial<NextjsConfig>) => {
    if (!config) return;

    const newConfig = { ...config, ...updates };
    setConfig(newConfig);
  }, [config]);

  const saveConfig = useCallback(async () => {
    if (!config || !userId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/integrations/nextjs/config', {
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
          description: 'Next.js integration settings have been saved',
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
      platform: 'nextjs',
      projects: [],
      deployments: [],
      builds: [],
      includeAnalytics: true,
      includeBuildLogs: true,
      includeEnvironmentVariables: false,
      realTimeSync: true,
      webhookEvents: ['deployment.created', 'deployment.ready', 'deployment.error', 'build.ready'],
      syncFrequency: 'realtime',
      dateRange: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
        end: new Date(),
      },
      maxProjects: 50,
      maxBuilds: 100,
      enableNotifications: true,
      backgroundSync: true,
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
export const useNextjsWebhooks = (userId: string, projectIds: string[] = []) => {
  const [updates, setUpdates] = useState<any[]>([]);

  useEffect(() => {
    if (!userId || projectIds.length === 0) return;

    // Setup WebSocket connection for real-time updates
    const ws = new WebSocket(`${process.env.NEXT_PUBLIC_WS_URL}/nextjs/webhooks`);

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
        if (['deployment.ready', 'deployment.error', 'build.error'].includes(data.event)) {
          const status = data.event.includes('error') ? 'error' : 'success';
          toast({
            title: `Next.js ${data.event}`,
            description: data.payload.projectName || 'Project update',
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