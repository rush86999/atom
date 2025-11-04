/**
 * Next.js Integration Type Definitions
 */

export interface NextjsProject {
  id: string;
  name: string;
  description?: string;
  status: 'active' | 'archived' | 'suspended';
  framework: 'nextjs' | 'react' | 'typescript';
  runtime: 'node' | 'edge';
  repository?: {
    provider: 'github' | 'gitlab' | 'bitbucket';
    url: string;
    branch: string;
  };
  deployment?: {
    platform: 'vercel' | 'netlify' | 'aws' | 'custom';
    url: string;
    environment: 'production' | 'staging' | 'development';
  };
  domains: string[];
  createdAt: string;
  updatedAt: string;
  lastDeployedAt?: string;
  buildStatus?: 'building' | 'ready' | 'error';
  team?: {
    id: string;
    name: string;
    members: NextjsTeamMember[];
  };
  metrics?: {
    pageViews: number;
    uniqueVisitors: number;
    bandwidth: number;
    buildTime: number;
    errors: number;
  };
  settings: {
    buildCommand: string;
    outputDirectory: string;
    installCommand: string;
    nodeVersion: string;
    environmentVariables: Record<string, string>;
  };
}

export interface NextjsTeamMember {
  id: string;
  name: string;
  email: string;
  role: 'owner' | 'admin' | 'developer' | 'viewer';
  avatar?: string;
  lastActiveAt?: string;
}

export interface NextjsBuild {
  id: string;
  projectId: string;
  status: 'pending' | 'building' | 'ready' | 'error' | 'canceled';
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  commit?: {
    hash: string;
    message: string;
    author: string;
    branch: string;
  };
  logs?: string[];
  metrics?: {
    buildTime: number;
    bundleSize: number;
    assetsCount: number;
    warnings: number;
    errors: number;
  };
  deployment?: {
    url: string;
    environment: string;
    preview?: boolean;
  };
}

export interface NextjsDeployment {
  id: string;
  projectId: string;
  buildId: string;
  url: string;
  environment: 'production' | 'preview' | 'canary';
  status: 'ready' | 'building' | 'error';
  createdAt: string;
  alias?: string[];
  metrics?: {
    pageViews: number;
    uniqueVisitors: number;
    bandwidth: number;
    errors: number;
    uptime: number;
  };
}

export interface NextjsEnvironmentVariable {
  id: string;
  key: string;
  value: string;
  target: 'production' | 'preview' | 'development' | 'all';
  type: 'plain' | 'secret' | 'system';
  updatedAt: string;
  updatedBy?: string;
}

export interface NextjsAnalytics {
  projectId: string;
  dateRange: {
    start: string;
    end: string;
  };
  metrics: {
    pageViews: number;
    uniqueVisitors: number;
    visits: number;
    bounceRate: number;
    avgSessionDuration: number;
    topPages: Array<{
      path: string;
      views: number;
      uniqueVisitors: number;
      bounceRate: number;
      avgLoadTime: number;
    }>;
    topReferrers: Array<{
      source: string;
      visitors: number;
      conversionRate: number;
    }>;
    devices: Array<{
      type: 'desktop' | 'mobile' | 'tablet';
      visitors: number;
      percentage: number;
    }>;
    browsers: Array<{
      name: string;
      visitors: number;
      percentage: number;
    }>;
    performance: {
      avgLoadTime: number;
      firstContentfulPaint: number;
      largestContentfulPaint: number;
      cumulativeLayoutShift: number;
    };
  };
}

export interface NextjsWebhookEvent {
  id: string;
  type: 'deployment.created' | 'deployment.ready' | 'deployment.error' | 'build.created' | 'build.ready' | 'build.error';
  projectId: string;
  data: any;
  createdAt: string;
}

export interface NextjsConfig {
  platform: 'nextjs';
  projects: string[];
  deployments: string[];
  builds: string[];
  includeAnalytics: boolean;
  includeBuildLogs: boolean;
  includeEnvironmentVariables: boolean;
  realTimeSync: boolean;
  webhookEvents: string[];
  syncFrequency: 'realtime' | 'hourly' | 'daily' | 'weekly';
  dateRange: {
    start: Date;
    end: Date;
  };
  maxProjects: number;
  maxBuilds: number;
  teamId?: string;
  accessToken?: string;
  refreshToken?: string;
  expiresAt?: Date;
}

export interface NextjsIntegrationProps {
  atomIngestionPipeline: any;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: any) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

export interface NextjsDataSourceConfig {
  name: string;
  platform: string;
  enabled: boolean;
  settings: NextjsConfig;
  health?: {
    connected: boolean;
    lastSync: string;
    errors: string[];
  };
}