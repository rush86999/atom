/**
 * ATOM Subscription Plans & Pricing Configuration
 * Enterprise-grade pricing tiers and monetization strategy
 * Supports monthly/annual billing, enterprise custom pricing, and marketplace
 */

import { SubscriptionPlan, PricingTier, PlanFeature, Addon } from './AtomRevenuePlatform';

// Platform Configuration
export const ATOM_PRICING_CONFIG = {
  currency: 'USD',
  taxSettings: {
    enabled: true,
    taxProvider: 'stripe',
    defaultTaxRate: 0,
    taxExemptRegions: ['US'],
    collectedBy: 'stripe' // 'stripe' | 'atom'
  },
  billing: {
    provider: 'stripe',
    stripeConfig: {
      apiKey: process.env.STRIPE_SECRET_KEY,
      webhookSecret: process.env.STRIPE_WEBHOOK_SECRET,
      publishableKey: process.env.STRIPE_PUBLISHABLE_KEY
    }
  },
  subscriptions: {
    freeTrialDays: 14,
    billingCycle: 'monthly',
    cancellationPolicy: {
      refundDays: 30,
      proRated: true,
      reasonRequired: true
    }
  },
  enterprise: {
    customPricing: true,
    contractManagement: true,
    quoteGeneration: true,
    salesIntegration: true,
    volumeDiscounts: true,
    minimumContractSize: 12, // months
    minimumSeats: 10
  }
};

// Pricing Tiers
export const ATOM_PRICING_TIERS: PricingTier[] = [
  {
    id: 'starter',
    name: 'Starter',
    rank: 1,
    basePrice: 0,
    multiplier: 1,
    description: 'Perfect for individuals and small teams',
    icon: '🌱',
    color: 'green',
    badgeColor: 'green',
    highlighted: false
  },
  {
    id: 'professional',
    name: 'Professional',
    rank: 2,
    basePrice: 29,
    multiplier: 1,
    description: 'Ideal for growing teams and professionals',
    icon: '⚡',
    color: 'blue',
    badgeColor: 'blue',
    highlighted: true
  },
  {
    id: 'business',
    name: 'Business',
    rank: 3,
    basePrice: 79,
    multiplier: 1,
    description: 'Complete solution for businesses',
    icon: '🚀',
    color: 'purple',
    badgeColor: 'purple',
    highlighted: false
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    rank: 4,
    basePrice: 199,
    multiplier: 1,
    description: 'Advanced features for large organizations',
    icon: '🏢',
    color: 'gray',
    badgeColor: 'gray',
    highlighted: false
  },
  {
    id: 'custom',
    name: 'Custom',
    rank: 5,
    basePrice: 0,
    multiplier: 1,
    description: 'Tailored solutions for specific needs',
    icon: '🎯',
    color: 'indigo',
    badgeColor: 'indigo',
    highlighted: false
  }
];

// Plan Features Configuration
export const ATOM_FEATURE_CATEGORIES = {
  integrations: {
    name: 'Integrations',
    description: 'Connect and manage your favorite tools',
    icon: '🔗'
  },
  ai: {
    name: 'AI & Automation',
    description: 'Advanced AI capabilities and automation',
    icon: '🤖'
  },
  workflows: {
    name: 'Workflows',
    description: 'Create and automate powerful workflows',
    icon: '⚙️'
  },
  collaboration: {
    name: 'Collaboration',
    description: 'Team collaboration and communication',
    icon: '👥'
  },
  security: {
    name: 'Security & Compliance',
    description: 'Enterprise-grade security and compliance',
    icon: '🔒'
  },
  support: {
    name: 'Support',
    description: 'Customer support and assistance',
    icon: '💬'
  },
  analytics: {
    name: 'Analytics & Insights',
    description: 'Detailed analytics and business insights',
    icon: '📊'
  },
  customization: {
    name: 'Customization',
    description: 'Custom branding and white-labeling',
    icon: '🎨'
  }
};

// Comprehensive Subscription Plans
export const ATOM_SUBSCRIPTION_PLANS: SubscriptionPlan[] = [
  // Starter Plan (Free)
  {
    id: 'starter',
    name: 'Starter',
    description: 'Get started with ATOM for free. Perfect for individuals and personal projects.',
    price: {
      monthly: 0,
      yearly: 0,
      currency: 'USD'
    },
    tier: ATOM_PRICING_TIERS[0],
    features: [
      // Integrations
      {
        id: 'integrations-basic',
        name: 'Basic Integrations',
        description: 'Connect up to 5 essential integrations',
        category: 'integrations',
        enabled: true,
        limit: 5,
        unit: 'integrations',
        icon: '🔗',
        tooltip: 'Includes Gmail, Google Drive, Slack, Trello, Notion'
      },
      {
        id: 'api-calls-limited',
        name: 'API Access',
        description: 'Limited API access for integrations',
        category: 'integrations',
        enabled: true,
        limit: 1000,
        unit: 'calls/month',
        icon: '🔌'
      },
      // AI Features
      {
        id: 'ai-basic-chat',
        name: 'AI Assistant',
        description: 'Basic AI-powered chat assistance',
        category: 'ai',
        enabled: true,
        limit: 50,
        unit: 'interactions/month',
        icon: '🤖',
        tooltip: 'General assistance and basic queries'
      },
      {
        id: 'ai-basic-workflows',
        name: 'Workflow Suggestions',
        description: 'AI suggests simple workflow optimizations',
        category: 'ai',
        enabled: true,
        icon: '💡'
      },
      // Workflows
      {
        id: 'workflows-basic',
        name: 'Basic Workflows',
        description: 'Create up to 10 simple workflows',
        category: 'workflows',
        enabled: true,
        limit: 10,
        unit: 'workflows',
        icon: '⚙️'
      },
      {
        id: 'triggers-basic',
        name: 'Automation Triggers',
        description: 'Basic trigger-based automation',
        category: 'workflows',
        enabled: true,
        icon: '⚡'
      },
      // Support
      {
        id: 'support-community',
        name: 'Community Support',
        description: 'Access to community forums and documentation',
        category: 'support',
        enabled: true,
        icon: '👥',
        tooltip: 'Get help from our community and extensive documentation'
      },
      // Security
      {
        id: 'security-basic',
        name: 'Standard Security',
        description: 'Standard encryption and data protection',
        category: 'security',
        enabled: true,
        icon: '🔒'
      }
    ],
    limits: {
      users: 1,
      workspaces: 1,
      workflows: 10,
      integrations: 5,
      apiCalls: 1000,
      storage: 2, // GB
      bandwidth: 50, // GB/month
      aiTokens: 50000,
      dataRetention: 30, // days
      customBranding: false,
      apiAccess: false
    },
    integrations: {
      count: 5,
      included: ['gmail', 'gdrive', 'slack', 'trello', 'notion'],
      premium: []
    },
    ai: {
      requestsPerMonth: 50,
      models: ['gpt-3.5-turbo'],
      advancedFeatures: ['basic_chat', 'simple_suggestions']
    },
    support: {
      level: 'community',
      responseTime: '72 hours',
      channels: ['community-forum', 'documentation'],
      hours: '24/7 (community)',
      escalation: false,
      dedicatedManager: false
    },
    sla: {
      uptime: 99.5,
      responseTime: 2000,
      dataLossProtection: true,
      backupFrequency: 'Weekly',
      recoveryTime: '48 hours'
    },
    addons: [],
    targeting: {
      userTypes: ['individual', 'freelancer', 'student'],
      companySizes: ['1-10'],
      industries: ['technology', 'creative', 'education'],
      useCases: ['personal-productivity', 'project-management', 'basic-automation']
    }
  },

  // Professional Plan
  {
    id: 'professional',
    name: 'Professional',
    description: 'Advanced features for professionals and growing teams. Includes all Starter features plus AI-powered automation.',
    price: {
      monthly: 29,
      yearly: 290,
      currency: 'USD'
    },
    tier: ATOM_PRICING_TIERS[1],
    features: [
      // All Starter Features
      ...ATOM_SUBSCRIPTION_PLANS[0].features.map(f => ({ ...f, enabled: true, limit: f.unlimited ? undefined : (f.limit || 0) * 3 })),
      
      // Enhanced Integrations
      {
        id: 'integrations-pro',
        name: 'Professional Integrations',
        description: 'Connect up to 20 integrations including premium services',
        category: 'integrations',
        enabled: true,
        limit: 20,
        unit: 'integrations',
        icon: '🔗',
        tooltip: 'Includes all Starter integrations plus GitHub, Jira, Asana, Monday, Figma'
      },
      {
        id: 'webhooks-pro',
        name: 'Webhooks & Real-time Sync',
        description: 'Advanced webhook support and real-time synchronization',
        category: 'integrations',
        enabled: true,
        icon: '🔔'
      },
      // Advanced AI
      {
        id: 'ai-pro-chat',
        name: 'Advanced AI Assistant',
        description: 'Enhanced AI with contextual understanding and voice support',
        category: 'ai',
        enabled: true,
        limit: 500,
        unit: 'interactions/month',
        icon: '🤖',
        tooltip: 'Voice recognition, context awareness, and advanced reasoning'
      },
      {
        id: 'ai-predictive-workflows',
        name: 'Predictive Workflow Generation',
        description: 'AI automatically suggests and creates workflows based on patterns',
        category: 'ai',
        enabled: true,
        icon: '🧠',
        tooltip: 'AI learns from your behavior and suggests optimizations'
      },
      {
        id: 'ai-automation-intelligence',
        name: 'Automation Intelligence',
        description: 'AI-powered insights and automation recommendations',
        category: 'ai',
        enabled: true,
        icon: '📊'
      },
      // Advanced Workflows
      {
        id: 'workflows-pro',
        name: 'Advanced Workflows',
        description: 'Create complex multi-step workflows with conditional logic',
        category: 'workflows',
        enabled: true,
        limit: 100,
        unit: 'workflows',
        icon: '⚙️'
      },
      {
        id: 'workflows-scheduled',
        name: 'Scheduled Workflows',
        description: 'Automate workflows on schedules and recurring patterns',
        category: 'workflows',
        enabled: true,
        icon: '📅'
      },
      {
        id: 'workflows-error-handling',
        name: 'Error Handling & Retry',
        description: 'Advanced error handling and retry mechanisms',
        category: 'workflows',
        enabled: true,
        icon: '🔄'
      },
      // Collaboration
      {
        id: 'team-collaboration',
        name: 'Team Collaboration',
        description: 'Share workflows and collaborate with team members',
        category: 'collaboration',
        enabled: true,
        limit: 5,
        unit: 'users',
        icon: '👥'
      },
      {
        id: 'activity-monitoring',
        name: 'Activity Monitoring',
        description: 'Monitor team activity and workflow performance',
        category: 'collaboration',
        enabled: true,
        icon: '📈'
      },
      // Analytics
      {
        id: 'analytics-pro',
        name: 'Advanced Analytics',
        description: 'Detailed usage analytics and performance insights',
        category: 'analytics',
        enabled: true,
        icon: '📊',
        tooltip: 'Track workflow performance, usage patterns, and ROI'
      },
      {
        id: 'custom-reports',
        name: 'Custom Reports',
        description: 'Generate custom reports and export data',
        category: 'analytics',
        enabled: true,
        icon: '📋'
      },
      // Support
      {
        id: 'support-pro',
        name: 'Priority Support',
        description: '24/7 email support with 24-hour response time',
        category: 'support',
        enabled: true,
        icon: '💬',
        tooltip: 'Faster response times and dedicated support team'
      },
      {
        id: 'support-video-calls',
        name: 'Video Call Support',
        description: 'Monthly video call support sessions',
        category: 'support',
        enabled: true,
        limit: 1,
        unit: 'calls/month',
        icon: '📹'
      },
      // Security
      {
        id: 'security-pro',
        name: 'Enhanced Security',
        description: 'Two-factor authentication and advanced security features',
        category: 'security',
        enabled: true,
        icon: '🔒'
      },
      {
        id: 'audit-logs',
        name: 'Audit Logs',
        description: 'Comprehensive audit logging and activity tracking',
        category: 'security',
        enabled: true,
        icon: '📝'
      }
    ],
    limits: {
      users: 5,
      workspaces: 3,
      workflows: 100,
      integrations: 20,
      apiCalls: 10000,
      storage: 20, // GB
      bandwidth: 500, // GB/month
      aiTokens: 500000,
      dataRetention: 90, // days
      customBranding: false,
      apiAccess: true
    },
    integrations: {
      count: 20,
      included: ['gmail', 'gdrive', 'slack', 'trello', 'notion', 'github', 'jira', 'asana', 'monday', 'figma'],
      premium: ['zapier', 'microsoft365']
    },
    ai: {
      requestsPerMonth: 500,
      models: ['gpt-4', 'claude-3'],
      advancedFeatures: ['voice_recognition', 'contextual_chat', 'predictive_workflows', 'automation_intelligence']
    },
    support: {
      level: 'standard',
      responseTime: '24 hours',
      channels: ['email', 'chat'],
      hours: '24/7',
      escalation: true,
      dedicatedManager: false
    },
    sla: {
      uptime: 99.8,
      responseTime: 1000,
      dataLossProtection: true,
      backupFrequency: 'Daily',
      recoveryTime: '24 hours'
    },
    addons: ['additional-users', 'extra-storage', 'premium-integrations'],
    targeting: {
      userTypes: ['professional', 'small-team', 'startup'],
      companySizes: ['2-50'],
      industries: ['technology', 'consulting', 'marketing', 'design', 'development'],
      useCases: ['team-productivity', 'project-management', 'advanced-automation', 'customer-service']
    }
  },

  // Business Plan
  {
    id: 'business',
    name: 'Business',
    description: 'Complete solution for businesses with advanced AI, enterprise integrations, and premium support.',
    price: {
      monthly: 79,
      yearly: 790,
      currency: 'USD'
    },
    tier: ATOM_PRICING_TIERS[2],
    features: [
      // All Professional Features
      ...ATOM_SUBSCRIPTION_PLANS[1].features.map(f => ({ 
        ...f, 
        enabled: true, 
        limit: f.unlimited ? undefined : (f.limit || 0) * 3,
        unit: f.unit
      })),
      
      // Unlimited Integrations
      {
        id: 'integrations-unlimited',
        name: 'Unlimited Integrations',
        description: 'Connect all 33+ available integrations and custom ones',
        category: 'integrations',
        enabled: true,
        unlimited: true,
        icon: '🔗',
        tooltip: 'Access to all ATOM integrations including enterprise services'
      },
      {
        id: 'custom-integrations',
        name: 'Custom Integrations',
        description: 'Build and deploy custom API integrations',
        category: 'integrations',
        enabled: true,
        limit: 5,
        unit: 'custom integrations',
        icon: '🔧'
      },
      // Enterprise AI
      {
        id: 'ai-enterprise',
        name: 'Enterprise AI Suite',
        description: 'Full AI suite with advanced models and unlimited usage',
        category: 'ai',
        enabled: true,
        limit: 2000,
        unit: 'interactions/month',
        icon: '🤖',
        tooltip: 'Access to GPT-4, Claude-3, and specialized enterprise models'
      },
      {
        id: 'ai-fine-tuning',
        name: 'AI Model Fine-Tuning',
        description: 'Fine-tune AI models on your business data',
        category: 'ai',
        enabled: true,
        limit: 1,
        unit: 'model/month',
        icon: '🎯'
      },
      {
        id: 'ai-workflow-optimization',
        name: 'Workflow AI Optimization',
        description: 'AI continuously optimizes your workflows for maximum efficiency',
        category: 'ai',
        enabled: true,
        icon: '⚡'
      },
      {
        id: 'ai-predictive-analytics',
        name: 'Predictive Analytics',
        description: 'AI-powered predictive analytics and forecasting',
        category: 'ai',
        enabled: true,
        icon: '📊'
      },
      // Advanced Workflows
      {
        id: 'workflows-unlimited',
        name: 'Unlimited Workflows',
        description: 'Create unlimited workflows of any complexity',
        category: 'workflows',
        enabled: true,
        unlimited: true,
        icon: '⚙️'
      },
      {
        id: 'workflows-visual-builder',
        name: 'Visual Workflow Builder',
        description: 'Drag-and-drop visual workflow builder',
        category: 'workflows',
        enabled: true,
        icon: '🎨'
      },
      {
        id: 'workflows-parallel-execution',
        name: 'Parallel Execution',
        description: 'Execute multiple workflows in parallel',
        category: 'workflows',
        enabled: true,
        icon: '⚡'
      },
      {
        id: 'workflows-marketplace',
        name: 'Workflow Marketplace',
        description: 'Access and share pre-built workflow templates',
        category: 'workflows',
        enabled: true,
        icon: '🏪'
      },
      // Enterprise Collaboration
      {
        id: 'team-unlimited',
        name: 'Unlimited Team Members',
        description: 'Add unlimited team members with role-based access',
        category: 'collaboration',
        enabled: true,
        limit: 50,
        unit: 'users',
        icon: '👥'
      },
      {
        id: 'workspaces-unlimited',
        name: 'Multiple Workspaces',
        description: 'Create separate workspaces for different teams/projects',
        category: 'collaboration',
        enabled: true,
        limit: 10,
        unit: 'workspaces',
        icon: '🏢'
      },
      {
        id: 'advanced-permissions',
        name: 'Advanced Permissions',
        description: 'Granular role-based access control and permissions',
        category: 'collaboration',
        enabled: true,
        icon: '🔐'
      },
      // Business Analytics
      {
        id: 'analytics-business',
        name: 'Business Intelligence',
        description: 'Advanced BI dashboards and business insights',
        category: 'analytics',
        enabled: true,
        icon: '📊',
        tooltip: 'Custom dashboards, KPI tracking, and business metrics'
      },
      {
        id: 'roi-analytics',
        name: 'ROI Analytics',
        description: 'Track and measure ROI of your automation workflows',
        category: 'analytics',
        enabled: true,
        icon: '💰'
      },
      {
        id: 'data-warehouse',
        name: 'Data Warehouse Integration',
        description: 'Connect to external data warehouses and BI tools',
        category: 'analytics',
        enabled: true,
        icon: '🗄️'
      },
      // Business Support
      {
        id: 'support-business',
        name: 'Business Support',
        description: '24/7 phone, email, and chat support with 1-hour response',
        category: 'support',
        enabled: true,
        icon: '💬',
        tooltip: 'Priority support with dedicated account manager'
      },
      {
        id: 'support-account-manager',
        name: 'Dedicated Account Manager',
        description: 'Personal account manager for your business',
        category: 'support',
        enabled: true,
        icon: '👤'
      },
      {
        id: 'support-training',
        name: 'Team Training Sessions',
        description: 'Monthly training sessions for your team',
        category: 'support',
        enabled: true,
        limit: 2,
        unit: 'sessions/month',
        icon: '🎓'
      },
      {
        id: 'support-implementation',
        name: 'Implementation Support',
        description: 'Help with onboarding and implementation',
        category: 'support',
        enabled: true,
        limit: 8,
        unit: 'hours/month',
        icon: '🚀'
      },
      // Enterprise Security
      {
        id: 'security-enterprise',
        name: 'Enterprise Security',
        description: 'Advanced security with SSO, SAML, and enterprise features',
        category: 'security',
        enabled: true,
        icon: '🔒'
      },
      {
        id: 'security-compliance',
        name: 'Compliance & Certifications',
        description: 'SOC 2, GDPR, HIPAA compliant (add-ons available)',
        category: 'security',
        enabled: true,
        icon: '✅'
      },
      {
        id: 'security-data-residency',
        name: 'Data Residency',
        description: 'Choose data center location for compliance',
        category: 'security',
        enabled: true,
        icon: '🌍'
      },
      // Customization
      {
        id: 'custom-branding',
        name: 'Custom Branding',
        description: 'White-label with custom branding and domain',
        category: 'customization',
        enabled: true,
        icon: '🎨'
      },
      {
        id: 'custom-domain',
        name: 'Custom Domain',
        description: 'Use your own domain for white-labeling',
        category: 'customization',
        enabled: true,
        icon: '🌐'
      }
    ],
    limits: {
      users: 50,
      workspaces: 10,
      workflows: -1, // unlimited
      integrations: -1, // unlimited
      apiCalls: 100000,
      storage: 200, // GB
      bandwidth: 2000, // GB/month
      aiTokens: 2000000,
      dataRetention: 365, // days
      customBranding: true,
      apiAccess: true
    },
    integrations: {
      count: -1, // unlimited
      included: Object.keys(require('../ui-shared/integrations/index').getAllIntegrations()),
      premium: ['sap', 'workday', 'salesforce', 'servicenow']
    },
    ai: {
      requestsPerMonth: 2000,
      models: ['gpt-4', 'claude-3-opus', 'custom-enterprise'],
      advancedFeatures: ['fine_tuning', 'workflow_optimization', 'predictive_analytics', 'enterprise_ai']
    },
    support: {
      level: 'premium',
      responseTime: '1 hour',
      channels: ['phone', 'email', 'chat', 'video'],
      hours: '24/7',
      escalation: true,
      dedicatedManager: true
    },
    sla: {
      uptime: 99.9,
      responseTime: 500,
      dataLossProtection: true,
      backupFrequency: 'Hourly',
      recoveryTime: '4 hours'
    },
    addons: [
      'additional-users', 'extra-storage', 'premium-integrations', 
      'compliance-hipaa', 'compliance-soc2', 'custom-training'
    ],
    targeting: {
      userTypes: ['business', 'enterprise', 'medium-team'],
      companySizes: ['50-1000'],
      industries: ['technology', 'finance', 'healthcare', 'manufacturing', 'consulting', 'retail'],
      useCases: ['enterprise-automation', 'business-process-optimization', 'compliance-automation', 'data-analytics']
    }
  },

  // Enterprise Plan
  {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'Complete enterprise solution with unlimited features, advanced AI, and dedicated support.',
    price: {
      monthly: 199,
      yearly: 1990,
      currency: 'USD'
    },
    tier: ATOM_PRICING_TIERS[3],
    features: [
      // All Business Features
      ...ATOM_SUBSCRIPTION_PLANS[2].features.map(f => ({ 
        ...f, 
        enabled: true, 
        limit: f.unlimited ? undefined : (f.limit || 0) * 2,
        unit: f.unit
      })),
      
      // Ultimate Features
      {
        id: 'ai-unlimited',
        name: 'Unlimited AI Usage',
        description: 'Unlimited AI interactions and advanced models',
        category: 'ai',
        enabled: true,
        unlimited: true,
        icon: '🤖',
        tooltip: 'Unlimited access to all AI features and models'
      },
      {
        id: 'ai-embedded-models',
        name: 'Embedded AI Models',
        description: 'Deploy custom AI models and fine-tuning on your data',
        category: 'ai',
        enabled: true,
        unlimited: true,
        icon: '🧠'
      },
      {
        id: 'ai-multi-agent',
        name: 'Multi-Agent AI System',
        description: 'Deploy multiple specialized AI agents for different tasks',
        category: 'ai',
        enabled: true,
        unlimited: true,
        icon: '🤹'
      },
      {
        id: 'workflows-multi-tenant',
        name: 'Multi-Tenant Workflows',
        description: 'Share workflows across organizations with proper isolation',
        category: 'workflows',
        enabled: true,
        unlimited: true,
        icon: '🏢'
      },
      {
        id: 'workflows-compliance',
        name: 'Compliance Workflows',
        description: 'Pre-built compliance and audit workflows',
        category: 'workflows',
        enabled: true,
        unlimited: true,
        icon: '✅'
      },
      {
        id: 'team-enterprise',
        name: 'Enterprise Team Management',
        description: 'Advanced team management with hierarchical permissions',
        category: 'collaboration',
        enabled: true,
        unlimited: true,
        icon: '👥'
      },
      {
        id: 'analytics-real-time',
        name: 'Real-time Analytics',
        description: 'Real-time data streaming and analytics',
        category: 'analytics',
        enabled: true,
        unlimited: true,
        icon: '📊'
      },
      {
        id: 'support-enterprise',
        name: 'Enterprise Support',
        description: '24/7 dedicated support with 15-minute response SLA',
        category: 'support',
        enabled: true,
        icon: '💬',
        tooltip: 'Dedicated support team and infrastructure monitoring'
      },
      {
        id: 'security-advanced',
        name: 'Advanced Security',
        description: 'Zero-trust security, encryption at rest and in transit',
        category: 'security',
        enabled: true,
        unlimited: true,
        icon: '🔒'
      },
      {
        id: 'custom-development',
        name: 'Custom Development',
        description: 'Custom feature development and engineering support',
        category: 'customization',
        enabled: true,
        limit: 20,
        unit: 'hours/month',
        icon: '🔧'
      }
    ],
    limits: {
      users: -1, // unlimited
      workspaces: -1, // unlimited
      workflows: -1, // unlimited
      integrations: -1, // unlimited
      apiCalls: -1, // unlimited
      storage: 1000, // GB
      bandwidth: -1, // unlimited
      aiTokens: -1, // unlimited
      dataRetention: -1, // unlimited
      customBranding: true,
      apiAccess: true
    },
    integrations: {
      count: -1, // unlimited
      included: Object.keys(require('../ui-shared/integrations/index').getAllIntegrations()),
      premium: ['sap', 'workday', 'salesforce', 'servicenow', 'oracle', 'adobe']
    },
    ai: {
      requestsPerMonth: -1, // unlimited
      models: ['gpt-4', 'claude-3-opus', 'custom-enterprise', 'specialized-domain'],
      advancedFeatures: ['embedded_models', 'multi_agent', 'real_time_processing', 'custom_training']
    },
    support: {
      level: 'enterprise',
      responseTime: '15 minutes',
      channels: ['phone', 'email', 'chat', 'video', 'onsite'],
      hours: '24/7',
      escalation: true,
      dedicatedManager: true
    },
    sla: {
      uptime: 99.99,
      responseTime: 200,
      dataLossProtection: true,
      backupFrequency: 'Real-time',
      recoveryTime: '1 hour'
    },
    addons: [
      'onsite-support', 'custom-training', 'dedicated-infrastructure', 
      'compliance-enterprise', 'advanced-monitoring'
    ],
    targeting: {
      userTypes: ['enterprise', 'large-corporation'],
      companySizes: ['1000+'],
      industries: ['technology', 'finance', 'healthcare', 'manufacturing', 'government'],
      useCases: ['enterprise-transformation', 'digital-workforce', 'compliance-automation', 'global-scalability']
    }
  }
];

// Premium Add-ons
export const ATOM_ADDONS: Addon[] = [
  // User-based Add-ons
  {
    id: 'additional-users',
    name: 'Additional Users',
    description: 'Add more users to your plan',
    price: 5,
    billing: 'monthly',
    category: 'integration',
    compatibleTiers: ['professional', 'business', 'enterprise'],
    features: ['extra_user_seats'],
    icon: '👥',
    popular: true
  },
  
  // Storage Add-ons
  {
    id: 'extra-storage',
    name: 'Extra Storage',
    description: 'Additional cloud storage for your data',
    price: 10,
    billing: 'monthly',
    category: 'storage',
    compatibleTiers: ['starter', 'professional', 'business'],
    features: ['extra_storage_space'],
    icon: '💾',
    popular: false
  },
  
  // AI Add-ons
  {
    id: 'ai-boost',
    name: 'AI Boost',
    description: 'Additional AI tokens and advanced models',
    price: 15,
    billing: 'monthly',
    category: 'ai',
    compatibleTiers: ['professional', 'business'],
    features: ['extra_ai_tokens', 'advanced_ai_models'],
    icon: '🚀',
    popular: true
  },
  
  // Integration Add-ons
  {
    id: 'premium-integrations',
    name: 'Premium Integrations',
    description: 'Access to enterprise integrations like SAP, Workday',
    price: 25,
    billing: 'monthly',
    category: 'integration',
    compatibleTiers: ['professional', 'business'],
    features: ['enterprise_integrations', 'advanced_webhooks'],
    icon: '🔗',
    popular: false
  },
  
  // Compliance Add-ons
  {
    id: 'compliance-hipaa',
    name: 'HIPAA Compliance',
    description: 'HIPAA compliant infrastructure and processes',
    price: 50,
    billing: 'monthly',
    category: 'security',
    compatibleTiers: ['business', 'enterprise'],
    features: ['hipaa_compliance', 'baa_agreement'],
    icon: '🏥',
    popular: false
  },
  
  {
    id: 'compliance-soc2',
    name: 'SOC 2 Compliance',
    description: 'SOC 2 Type II compliance and reporting',
    price: 75,
    billing: 'monthly',
    category: 'security',
    compatibleTiers: ['business', 'enterprise'],
    features: ['soc2_compliance', 'audit_reports'],
    icon: '📋',
    popular: false
  },
  
  // Support Add-ons
  {
    id: 'custom-training',
    name: 'Custom Team Training',
    description: 'Customized training sessions for your team',
    price: 500,
    billing: 'one-time',
    category: 'support',
    compatibleTiers: ['professional', 'business', 'enterprise'],
    features: ['custom_training_curriculum', 'hands_on_workshops'],
    icon: '🎓',
    popular: false
  },
  
  {
    id: 'onsite-support',
    name: 'Onsite Support',
    description: 'Dedicated onsite support and implementation',
    price: 2000,
    billing: 'monthly',
    category: 'support',
    compatibleTiers: ['enterprise'],
    features: ['onsite_engineer', 'implementation_support', 'emergency_response'],
    icon: '🏢',
    popular: false
  },
  
  // Infrastructure Add-ons
  {
    id: 'dedicated-infrastructure',
    name: 'Dedicated Infrastructure',
    description: 'Dedicated cloud infrastructure for maximum performance',
    price: 1000,
    billing: 'monthly',
    category: 'security',
    compatibleTiers: ['enterprise'],
    features: ['dedicated_servers', 'custom_vpc', 'advanced_monitoring'],
    icon: '🖥️',
    popular: false
  },
  
  {
    id: 'advanced-monitoring',
    name: 'Advanced Monitoring',
    description: 'Enterprise-grade monitoring and alerting',
    price: 100,
    billing: 'monthly',
    category: 'security',
    compatibleTiers: ['business', 'enterprise'],
    features: ['advanced_metrics', 'custom_alerts', 'performance_analysis'],
    icon: '📊',
    popular: false
  }
];

// Enterprise Custom Pricing
export const ATOM_ENTERPRISE_PRICING = {
  minimumSeats: 10,
  minimumContractMonths: 12,
  volumeDiscounts: [
    { seats: 10, discount: 0 },
    { seats: 25, discount: 0.10 },
    { seats: 50, discount: 0.20 },
    { seats: 100, discount: 0.30 },
    { seats: 250, discount: 0.40 },
    { seats: 500, discount: 0.45 },
    { seats: 1000, discount: 0.50 }
  ],
  contractDiscounts: [
    { months: 12, discount: 0 },
    { months: 24, discount: 0.10 },
    { months: 36, discount: 0.15 },
    { months: 48, discount: 0.20 },
    { months: 60, discount: 0.25 }
  ],
  customFeatures: [
    'dedicated_infrastructure',
    'custom_ai_models',
    'white_label_solution',
    'api_customization',
    'data_residency_options',
    'custom_compliance_requirements'
  ]
};

// Pricing Helper Functions
export const calculatePlanPrice = (planId: string, billingCycle: 'monthly' | 'yearly', users?: number, addons?: string[]): PriceCalculation => {
  const plan = ATOM_SUBSCRIPTION_PLANS.find(p => p.id === planId);
  if (!plan) {
    throw new Error(`Plan ${planId} not found`);
  }
  
  const basePrice = billingCycle === 'yearly' ? plan.price.yearly : plan.price.monthly;
  const yearlyDiscount = billingCycle === 'yearly' ? 0.17 : 0; // 17% discount for yearly
  const monthlyEquivalent = basePrice / 12;
  
  let totalPrice = basePrice;
  let addonPrice = 0;
  let userPrice = 0;
  let volumeDiscount = 0;
  
  // Calculate user-based pricing for enterprise
  if (planId === 'enterprise' && users && users > 10) {
    userPrice = calculateEnterpriseUserPricing(users, basePrice);
    totalPrice = userPrice;
    volumeDiscount = basePrice - userPrice;
  }
  
  // Calculate addon pricing
  if (addons && addons.length > 0) {
    addonPrice = addons.reduce((total, addonId) => {
      const addon = ATOM_ADDONS.find(a => a.id === addonId);
      if (addon && addon.compatibleTiers.includes(planId)) {
        const price = addon.billing === 'monthly' ? addon.price : addon.price * 12;
        return total + (billingCycle === 'yearly' && addon.billing === 'monthly' ? price * 0.83 : price);
      }
      return total;
    }, 0);
    totalPrice += addonPrice;
  }
  
  return {
    basePrice,
    userPrice,
    addonPrice,
    volumeDiscount,
    yearlyDiscount: yearlyDiscount > 0 ? basePrice * yearlyDiscount : 0,
    totalPrice,
    monthlyEquivalent: totalPrice / (billingCycle === 'yearly' ? 12 : 1),
    savings: {
      yearly: yearlyDiscount > 0 ? basePrice * yearlyDiscount * 12 : 0,
      volume: volumeDiscount,
      total: (yearlyDiscount > 0 ? basePrice * yearlyDiscount * 12 : 0) + volumeDiscount
    },
    currency: 'USD',
    billingCycle
  };
};

const calculateEnterpriseUserPricing = (users: number, basePrice: number): number => {
  const perSeatPrice = basePrice / 10; // Base price assumes 10 seats
  const totalPrice = perSeatPrice * users;
  
  // Apply volume discounts
  const discount = ATOM_ENTERPRISE_PRICING.volumeDiscounts
    .reverse()
    .find(d => users >= d.seats)?.discount || 0;
  
  return totalPrice * (1 - discount);
};

export interface PriceCalculation {
  basePrice: number;
  userPrice: number;
  addonPrice: number;
  volumeDiscount: number;
  yearlyDiscount: number;
  totalPrice: number;
  monthlyEquivalent: number;
  savings: {
    yearly: number;
    volume: number;
    total: number;
  };
  currency: string;
  billingCycle: 'monthly' | 'yearly';
}

// Feature Comparison Helper
export const getFeatureComparison = (planIds: string[]): FeatureComparison => {
  const plans = planIds.map(id => ATOM_SUBSCRIPTION_PLANS.find(p => p.id === id)).filter(Boolean) as SubscriptionPlan[];
  const allFeatures = [...new Set(plans.flatMap(p => p.features.map(f => f.id)))];
  
  const comparison: FeatureComparison = {
    plans,
    features: allFeatures.map(featureId => {
      const featureData = plans.flatMap(p => p.features.filter(f => f.id === featureId));
      const feature = featureData[0];
      
      return {
        id: featureId,
        name: feature?.name || featureId,
        description: feature?.description || '',
        category: feature?.category || 'general',
        availability: plans.map(plan => {
          const planFeature = plan.features.find(f => f.id === featureId);
          return {
            planId: plan.id,
            available: !!planFeature?.enabled,
            limit: planFeature?.limit,
            unlimited: planFeature?.unlimited,
            unit: planFeature?.unit
          };
        })
      };
    })
  };
  
  return comparison;
};

export interface FeatureComparison {
  plans: SubscriptionPlan[];
  features: FeatureComparisonItem[];
}

export interface FeatureComparisonItem {
  id: string;
  name: string;
  description: string;
  category: string;
  availability: FeatureAvailability[];
}

export interface FeatureAvailability {
  planId: string;
  available: boolean;
  limit?: number;
  unlimited?: boolean;
  unit?: string;
}

export default {
  ATOM_PRICING_CONFIG,
  ATOM_PRICING_TIERS,
  ATOM_SUBSCRIPTION_PLANS,
  ATOM_ADDONS,
  ATOM_ENTERPRISE_PRICING,
  calculatePlanPrice,
  getFeatureComparison
};