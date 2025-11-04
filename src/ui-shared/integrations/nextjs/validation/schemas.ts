/**
 * Next.js Integration Validation Schemas
 * Data validation and schema definitions for Next.js/Vercel integration
 */

import { z } from 'zod';

// Base schemas
const DateSchema = z.string().datetime().optional();
const UrlSchema = z.string().url().optional();
const NonEmptyString = z.string().min(1);

// Next.js Project Schema
export const NextjsProjectSchema = z.object({
  id: NonEmptyString,
  name: NonEmptyString,
  description: z.string().optional(),
  status: z.enum(['active', 'archived', 'suspended']),
  framework: z.enum(['nextjs', 'react', 'typescript', 'vue', 'angular', 'svelte', 'nuxt']),
  runtime: z.enum(['node', 'edge']),
  repository: z.object({
    provider: z.enum(['github', 'gitlab', 'bitbucket']),
    url: UrlSchema,
    branch: NonEmptyString
  }).optional(),
  deployment: z.object({
    platform: z.enum(['vercel', 'netlify', 'aws', 'custom']),
    url: UrlSchema,
    environment: z.enum(['production', 'staging', 'development'])
  }).optional(),
  domains: z.array(NonEmptyString).default([]),
  createdAt: DateSchema,
  updatedAt: DateSchema,
  lastDeployedAt: DateSchema,
  buildStatus: z.enum(['building', 'ready', 'error', 'canceled']).optional(),
  team: z.object({
    id: NonEmptyString,
    name: NonEmptyString,
    members: z.array(z.object({
      id: NonEmptyString,
      name: NonEmptyString,
      email: z.string().email(),
      role: z.enum(['owner', 'admin', 'developer', 'viewer']),
      avatar: UrlSchema,
      lastActiveAt: DateSchema
    }))
  }).optional(),
  metrics: z.object({
    pageViews: z.number().int().min(0),
    uniqueVisitors: z.number().int().min(0),
    bandwidth: z.number().min(0),
    buildTime: z.number().int().min(0),
    errors: z.number().int().min(0)
  }).optional(),
  settings: z.object({
    buildCommand: NonEmptyString,
    outputDirectory: NonEmptyString,
    installCommand: NonEmptyString,
    nodeVersion: NonEmptyString,
    environmentVariables: z.record(z.string(), z.string())
  })
});

// Next.js Build Schema
export const NextjsBuildSchema = z.object({
  id: NonEmptyString,
  projectId: NonEmptyString,
  status: z.enum(['pending', 'building', 'ready', 'error', 'canceled']),
  createdAt: DateSchema,
  startedAt: DateSchema,
  completedAt: DateSchema,
  duration: z.number().int().min(0).optional(),
  commit: z.object({
    hash: NonEmptyString,
    message: z.string(),
    author: NonEmptyString,
    branch: NonEmptyString
  }).optional(),
  logs: z.array(z.string()).optional(),
  metrics: z.object({
    buildTime: z.number().int().min(0),
    bundleSize: z.number().min(0),
    assetsCount: z.number().int().min(0),
    warnings: z.number().int().min(0),
    errors: z.number().int().min(0)
  }).optional(),
  deployment: z.object({
    url: UrlSchema,
    environment: z.enum(['production', 'preview', 'canary']),
    preview: z.boolean().default(false)
  }).optional()
});

// Next.js Deployment Schema
export const NextjsDeploymentSchema = z.object({
  id: NonEmptyString,
  projectId: NonEmptyString,
  buildId: NonEmptyString,
  url: UrlSchema,
  environment: z.enum(['production', 'preview', 'canary']),
  status: z.enum(['ready', 'building', 'error']),
  createdAt: DateSchema,
  alias: z.array(NonEmptyString).default([]),
  metrics: z.object({
    pageViews: z.number().int().min(0),
    uniqueVisitors: z.number().int().min(0),
    bandwidth: z.number().min(0),
    errors: z.number().int().min(0),
    uptime: z.number().min(0).max(1)
  }).optional()
});

// Next.js Analytics Schema
export const NextjsAnalyticsSchema = z.object({
  projectId: NonEmptyString,
  dateRange: z.object({
    start: NonEmptyString,
    end: NonEmptyString
  }),
  metrics: z.object({
    pageViews: z.number().int().min(0),
    uniqueVisitors: z.number().int().min(0),
    visits: z.number().int().min(0),
    bounceRate: z.number().min(0).max(1),
    avgSessionDuration: z.number().min(0),
    topPages: z.array(z.object({
      path: NonEmptyString,
      views: z.number().int().min(0),
      uniqueVisitors: z.number().int().min(0),
      bounceRate: z.number().min(0).max(1),
      avgLoadTime: z.number().min(0)
    })),
    topReferrers: z.array(z.object({
      source: NonEmptyString,
      visitors: z.number().int().min(0),
      conversionRate: z.number().min(0).max(1)
    })),
    devices: z.array(z.object({
      type: z.enum(['desktop', 'mobile', 'tablet']),
      visitors: z.number().int().min(0),
      percentage: z.number().min(0).max(1)
    })),
    browsers: z.array(z.object({
      name: NonEmptyString,
      visitors: z.number().int().min(0),
      percentage: z.number().min(0).max(1)
    })),
    performance: z.object({
      avgLoadTime: z.number().min(0),
      firstContentfulPaint: z.number().min(0),
      largestContentfulPaint: z.number().min(0),
      cumulativeLayoutShift: z.number().min(0)
    })
  })
});

// Next.js Environment Variable Schema
export const NextjsEnvironmentVariableSchema = z.object({
  id: NonEmptyString,
  key: NonEmptyString,
  value: NonEmptyString,
  target: z.enum(['production', 'preview', 'development', 'all']),
  type: z.enum(['plain', 'secret', 'system']),
  updatedAt: DateSchema,
  updatedBy: NonEmptyString.optional()
});

// Next.js Configuration Schema
export const NextjsConfigSchema = z.object({
  platform: z.literal('nextjs'),
  projects: z.array(NonEmptyString).default([]),
  deployments: z.array(NonEmptyString).default([]),
  builds: z.array(NonEmptyString).default([]),
  includeAnalytics: z.boolean().default(true),
  includeBuildLogs: z.boolean().default(true),
  includeEnvironmentVariables: z.boolean().default(false),
  realTimeSync: z.boolean().default(true),
  webhookEvents: z.array(z.enum([
    'deployment.created',
    'deployment.ready', 
    'deployment.error',
    'build.created',
    'build.ready',
    'build.error'
  ])).default([
    'deployment.created',
    'deployment.ready',
    'deployment.error',
    'build.ready'
  ]),
  syncFrequency: z.enum(['realtime', 'hourly', 'daily', 'weekly']).default('realtime'),
  dateRange: z.object({
    start: z.date(),
    end: z.date()
  }),
  maxProjects: z.number().int().min(1).max(1000).default(50),
  maxBuilds: z.number().int().min(1).max(1000).default(100),
  teamId: NonEmptyString.optional(),
  accessToken: NonEmptyString.optional(),
  refreshToken: NonEmptyString.optional(),
  expiresAt: z.date().optional()
});

// OAuth Request Schema
export const NextjsOAuthRequestSchema = z.object({
  user_id: NonEmptyString,
  scopes: z.array(NonEmptyString).default(['read', 'write', 'projects', 'deployments', 'builds']),
  platform: z.enum(['web', 'tauri', 'nextjs']).default('web')
});

// OAuth Callback Schema
export const NextjsOAuthCallbackSchema = z.object({
  code: NonEmptyString,
  state: z.string().optional(),
  platform: z.enum(['web', 'tauri', 'nextjs']).default('web')
});

// API Request Schemas
export const NextjsProjectsRequestSchema = z.object({
  user_id: NonEmptyString,
  limit: z.number().int().min(1).max(1000).default(50),
  status: z.enum(['active', 'archived', 'suspended', 'all']).default('active'),
  include_builds: z.boolean().default(false),
  include_deployments: z.boolean().default(true)
});

export const NextjsAnalyticsRequestSchema = z.object({
  user_id: NonEmptyString,
  project_id: NonEmptyString,
  date_range: z.object({
    start: NonEmptyString,
    end: NonEmptyString
  }).optional(),
  metrics: z.array(NonEmptyString).default([
    'pageViews',
    'uniqueVisitors', 
    'bounceRate',
    'avgSessionDuration'
  ])
});

export const NextjsBuildsRequestSchema = z.object({
  user_id: NonEmptyString,
  project_id: NonEmptyString,
  status: z.enum(['pending', 'building', 'ready', 'error', 'canceled', 'all']).default('all'),
  limit: z.number().int().min(1).max(100).default(20),
  include_logs: z.boolean().default(false)
});

export const NextjsDeployRequestSchema = z.object({
  user_id: NonEmptyString,
  project_id: NonEmptyString,
  branch: NonEmptyString.default('main'),
  force: z.boolean().default(false)
});

export const NextjsEnvironmentVariablesRequestSchema = z.object({
  user_id: NonEmptyString,
  project_id: NonEmptyString,
  action: z.enum(['list', 'create', 'update', 'delete']).default('list'),
  key: NonEmptyString.optional(),
  value: NonEmptyString.optional(),
  target: z.array(z.enum(['production', 'preview', 'development'])).default(['production', 'preview']),
  type: z.enum(['plain', 'secret', 'system']).default('plain')
});

// Validation Functions
export const validateNextjsProject = (data: unknown) => {
  return NextjsProjectSchema.safeParse(data);
};

export const validateNextjsBuild = (data: unknown) => {
  return NextjsBuildSchema.safeParse(data);
};

export const validateNextjsDeployment = (data: unknown) => {
  return NextjsDeploymentSchema.safeParse(data);
};

export const validateNextjsAnalytics = (data: unknown) => {
  return NextjsAnalyticsSchema.safeParse(data);
};

export const validateNextjsConfig = (data: unknown) => {
  return NextjsConfigSchema.safeParse(data);
};

export const validateNextjsOAuthRequest = (data: unknown) => {
  return NextjsOAuthRequestSchema.safeParse(data);
};

export const validateNextjsOAuthCallback = (data: unknown) => {
  return NextjsOAuthCallbackSchema.safeParse(data);
};

export const validateNextjsProjectsRequest = (data: unknown) => {
  return NextjsProjectsRequestSchema.safeParse(data);
};

export const validateNextjsAnalyticsRequest = (data: unknown) => {
  return NextjsAnalyticsRequestSchema.safeParse(data);
};

export const validateNextjsBuildsRequest = (data: unknown) => {
  return NextjsBuildsRequestSchema.safeParse(data);
};

export const validateNextjsDeployRequest = (data: unknown) => {
  return NextjsDeployRequestSchema.safeParse(data);
};

export const validateNextjsEnvironmentVariablesRequest = (data: unknown) => {
  return NextjsEnvironmentVariablesRequestSchema.safeParse(data);
};

// Error Messages
export const NextjsValidationErrors = {
  project: {
    invalid: 'Invalid project data format',
    missingId: 'Project ID is required',
    missingName: 'Project name is required',
    invalidStatus: 'Invalid project status',
    invalidFramework: 'Invalid framework',
    invalidRuntime: 'Invalid runtime'
  },
  build: {
    invalid: 'Invalid build data format',
    missingId: 'Build ID is required',
    missingProjectId: 'Project ID is required',
    invalidStatus: 'Invalid build status'
  },
  deployment: {
    invalid: 'Invalid deployment data format',
    missingId: 'Deployment ID is required',
    missingProjectId: 'Project ID is required',
    invalidUrl: 'Invalid deployment URL'
  },
  config: {
    invalid: 'Invalid configuration format',
    invalidPlatform: 'Platform must be "nextjs"',
    invalidSyncFrequency: 'Invalid sync frequency',
    invalidDateRange: 'Invalid date range',
    invalidMaxProjects: 'Max projects must be between 1 and 1000'
  },
  oauth: {
    invalidRequest: 'Invalid OAuth request format',
    missingUserId: 'User ID is required',
    invalidScopes: 'Invalid OAuth scopes',
    invalidPlatform: 'Invalid platform'
  }
};

// Type Guards
export const isNextjsProject = (data: unknown): data is z.infer<typeof NextjsProjectSchema> => {
  return NextjsProjectSchema.safeParse(data).success;
};

export const isNextjsBuild = (data: unknown): data is z.infer<typeof NextjsBuildSchema> => {
  return NextjsBuildSchema.safeParse(data).success;
};

export const isNextjsDeployment = (data: unknown): data is z.infer<typeof NextjsDeploymentSchema> => {
  return NextjsDeploymentSchema.safeParse(data).success;
};

export const isNextjsAnalytics = (data: unknown): data is z.infer<typeof NextjsAnalyticsSchema> => {
  return NextjsAnalyticsSchema.safeParse(data).success;
};

export const isNextjsConfig = (data: unknown): data is z.infer<typeof NextjsConfigSchema> => {
  return NextjsConfigSchema.safeParse(data).success;
};

// Default Values
export const DefaultNextjsConfig = {
  platform: 'nextjs' as const,
  projects: [],
  deployments: [],
  builds: [],
  includeAnalytics: true,
  includeBuildLogs: true,
  includeEnvironmentVariables: false,
  realTimeSync: true,
  webhookEvents: ['deployment.created', 'deployment.ready', 'deployment.error', 'build.ready'],
  syncFrequency: 'realtime' as const,
  dateRange: {
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    end: new Date()
  },
  maxProjects: 50,
  maxBuilds: 100
};

// Type Exports
export type NextjsProject = z.infer<typeof NextjsProjectSchema>;
export type NextjsBuild = z.infer<typeof NextjsBuildSchema>;
export type NextjsDeployment = z.infer<typeof NextjsDeploymentSchema>;
export type NextjsAnalytics = z.infer<typeof NextjsAnalyticsSchema>;
export type NextjsEnvironmentVariable = z.infer<typeof NextjsEnvironmentVariableSchema>;
export type NextjsConfig = z.infer<typeof NextjsConfigSchema>;
export type NextjsOAuthRequest = z.infer<typeof NextjsOAuthRequestSchema>;
export type NextjsOAuthCallback = z.infer<typeof NextjsOAuthCallbackSchema>;
export type NextjsProjectsRequest = z.infer<typeof NextjsProjectsRequestSchema>;
export type NextjsAnalyticsRequest = z.infer<typeof NextjsAnalyticsRequestSchema>;
export type NextjsBuildsRequest = z.infer<typeof NextjsBuildsRequestSchema>;
export type NextjsDeployRequest = z.infer<typeof NextjsDeployRequestSchema>;
export type NextjsEnvironmentVariablesRequest = z.infer<typeof NextjsEnvironmentVariablesRequestSchema>;