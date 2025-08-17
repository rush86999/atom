<file_path>
atom/src/templates/advancedWorkflowTemplates.ts
</file_path>

import { WorkflowDefinition } from '../orchestration/conversationalWorkflowManager';

export const AdvancedWorkflowTemplates = {
  // Business Intelligence & Analytics Workflow
  businessIntelligence: {
    id: 'template-business-intelligence-001',
    name: 'Business Intelligence Automation',
    description: 'Comprehensive financial analysis, market research, and competitor monitoring with automated reporting and strategic recommendations',
    category: 'analytics',
    complexity: 'high',
    estimatedSetupTime: '30-45 minutes',
    expectedMonthlyImpact: '10-15% improvement in data-driven decision making',
    tags: ['finance', 'research', 'dashboards', 'predictions', 'competitors'],

    trigger: {
      type: 'scheduled',
      schedule: '0 9 * * 1' // Every Monday at 9 AM
    },

    actions: [
      {
        type: 'skill_execution',
        description: 'Collect financial data from all connected accounts',
        parameters: {
          skill: 'financeSkillIndex.getFullFinancialSnapshot',
          frequency: 'weekly',
          dataPoints: ['balance_sheet', 'profit_loss', 'cash_flow', 'budget']
        },
        retryPolicy: { maxAttempts: 3, delayBetweenRetries: 10000 },
        timeout: 300000
      },
      {
        type: 'skill_execution',
        description: 'Conduct comprehensive competitor research',
        parameters: {
          skill: 'advancedResearchSkill.competitorAnalysis',
          scope: 'industry_wide',
          competitors: 'auto_detect',
          metrics: ['pricing', 'marketing_spend', 'social_engagement', 'web_traffic', 'hiring_activity']
        }
      },
      {
        type: 'skill_execution',
        description: 'Generate market intelligence report',
        parameters: {
          skill: 'dataAnalystSkill.generateExecutiveSummary',
          dataTypes: ['financial', 'competitive', 'market'],
          audience: 'executive',
          format: 'executive_summary'
        }
      },
      {
        type: 'notification',
        description: 'Send report via email and Slack',
        parameters: {
          channels: ['email', 'slack'],
          recipients: 'financial_team',
          subject: 'Weekly Financial Intelligence Report'
        }
      },
      {
        type: 'conditional_branch',
        description: 'Alert if unusual patterns detected',
        parameters: {
          condition: 'unusual_variance > 15% OR competitor_advantage_detected',
          actionOnTrue: 'high_priority_alert',
          template: 'executive_briefing'
        }
      }
    ],

    successMetrics: {
      dataFreshness: '< 6 hours',
      reportAccuracy: '98%+',
      decisionImpactScore: 'measured quarterly',
      alertRelevance: '90%+'
    }
  },

  // Customer Success Automation
  customerSuccess: {
    id: 'template-customer-success-001',
    name: 'Customer Success Proactive Management',
    description: 'Proactive customer health monitoring, churn prediction, and automated intervention workflows',
    category: 'customer_relationship',
    complexity: 'medium',
    estimatedSetupTime: '20-30 minutes',
    expectedMonthlyImpact: '20-30% reduction in churn rate',
    tags: ['crm', 'customers', 'prediction', 'retention', 'engagement'],

    trigger: {
      type: 'intent_match',
      intentCriteria: {
        primaryIntent: 'customer_health_check',
        confidenceThreshold: 0.8,
        requiredEntities: ['customer_id', 'health_score']
      }
    },

    actions: [
      {
        type: 'skill_execution',
        description: 'Calculate comprehensive customer health score',
        parameters: {
          skill: 'salesforceSkills.calculateHealthScore',
          factors: ['product_usage', 'support_tickets', 'contract_value', 'engagement_frequency', 'satisfaction_surveys']
        }
      },
      {
        type: 'conditional_branch',
        description: 'Determine risk level and intervention needed',
        parameters: {
          condition: 'health_score < 30 OR contract_renewal_within_30_days',
          conditions: [
            { threshold: 80, action: 'loyalty_program' },
            { threshold: 50, action: 'check_in_call' },
            { threshold: 30, action: 'escalated_success_manager' },
            { threshold: 20, action: 'executive_intervention' }
          ]
        }
      },
      {
        type: 'skill_execution',
        description: 'Generate personalized retention plan',
        parameters: {
          skill: 'customerSupportManagerSkills.createRetentionStrategy',
          healthScore: 'auto_detected',
          customerTier: 'auto_assess',
          historicalData: 'included'
        }
      },
      {
        type: 'notification',
        description: 'Alert appropriate
