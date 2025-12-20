import { WorkflowDefinition } from "../orchestration/conversationalWorkflowManager";

export const AdvancedWorkflowTemplates = {
  // Business Intelligence & Analytics Workflow
  businessIntelligence: {
    id: "template-business-intelligence-001",
    name: "Business Intelligence Automation",
    description:
      "Comprehensive financial analysis, market research, and competitor monitoring with automated reporting and strategic recommendations",
    category: "analytics",
    complexity: "high",
    estimatedSetupTime: "30-45 minutes",
    expectedMonthlyImpact: "10-15% improvement in data-driven decision making",
    tags: ["finance", "research", "dashboards", "predictions", "competitors"],

    trigger: {
      type: "scheduled",
      schedule: "0 9 * * 1", // Every Monday at 9 AM
    },

    actions: [
      {
        type: "skill_execution",
        description: "Collect financial data from all connected accounts",
        parameters: {
          skill: "financeSkillIndex.getFullFinancialSnapshot",
          frequency: "weekly",
          dataPoints: ["balance_sheet", "profit_loss", "cash_flow", "budget"],
        },
        retryPolicy: { maxAttempts: 3, delayBetweenRetries: 10000 },
        timeout: 300000,
      },
      {
        type: "skill_execution",
        description: "Conduct comprehensive competitor research",
        parameters: {
          skill: "advancedResearchSkill.competitorAnalysis",
          scope: "industry_wide",
          competitors: "auto_detect",
          metrics: [
            "pricing",
            "marketing_spend",
            "social_engagement",
            "web_traffic",
            "hiring_activity",
          ],
        },
      },
      {
        type: "skill_execution",
        description: "Generate market intelligence report",
        parameters: {
          skill: "dataAnalystSkill.generateExecutiveSummary",
          dataTypes: ["financial", "competitive", "market"],
          audience: "executive",
          format: "executive_summary",
        },
      },
      {
        type: "notification",
        description: "Send report via email and Slack",
        parameters: {
          channels: ["email", "slack"],
          recipients: "financial_team",
          subject: "Weekly Financial Intelligence Report",
        },
      },
      {
        type: "conditional_branch",
        description: "Alert if unusual patterns detected",
        parameters: {
          condition: "unusual_variance > 15% OR competitor_advantage_detected",
          actionOnTrue: "high_priority_alert",
          template: "executive_briefing",
        },
      },
    ],

    successMetrics: {
      dataFreshness: "< 6 hours",
      reportAccuracy: "98%+",
      decisionImpactScore: "measured quarterly",
      alertRelevance: "90%+",
    },
  },

  // Customer Success Automation
  customerSuccess: {
    id: "template-customer-success-001",
    name: "Customer Success Proactive Management",
    description:
      "Proactive customer health monitoring, churn prediction, and automated intervention workflows",
    category: "customer_relationship",
    complexity: "medium",
    estimatedSetupTime: "20-30 minutes",
    expectedMonthlyImpact: "20-30% reduction in churn rate",
    tags: ["crm", "customers", "prediction", "retention", "engagement"],

    trigger: {
      type: "intent_match",
      intentCriteria: {
        primaryIntent: "customer_health_check",
        confidenceThreshold: 0.8,
        requiredEntities: ["customer_id", "health_score"],
      },
    },

    actions: [
      {
        type: "skill_execution",
        description: "Calculate comprehensive customer health score",
        parameters: {
          skill: "salesforceSkills.calculateHealthScore",
          factors: [
            "product_usage",
            "support_tickets",
            "contract_value",
            "engagement_frequency",
            "satisfaction_surveys",
          ],
        },
      },
      {
        type: "conditional_branch",
        description: "Determine risk level and intervention needed",
        parameters: {
          condition: "health_score < 30 OR contract_renewal_within_30_days",
          conditions: [
            { threshold: 80, action: "loyalty_program" },
            { threshold: 50, action: "check_in_call" },
            { threshold: 30, action: "escalated_success_manager" },
            { threshold: 20, action: "executive_intervention" },
          ],
        },
      },
      {
        type: "skill_execution",
        description: "Generate personalized retention plan",
        parameters: {
          skill: "customerSupportManagerSkills.createRetentionStrategy",
          healthScore: "auto_detected",
          customerTier: "auto_assess",
          historicalData: "included",
        },
      },
      {
        type: "notification",
        description: "Alert appropriate team members",
        parameters: {
          channels: ["slack", "email", "sms"],
          recipients: "success_team",
          priority: "high",
          messageTemplate: "customer_intervention_needed",
        },
      },
      {
        type: "skill_execution",
        description: "Schedule follow-up check-in",
        parameters: {
          skill: "calendarSkills.scheduleMeeting",
          participants: "customer_success_manager",
          duration: "30 minutes",
          topic: "customer_health_review",
        },
      },
    ],

    successMetrics: {
      responseTime: "< 2 hours",
      churnPreventionRate: "85%+",
      customerSatisfaction: "measured quarterly",
      interventionSuccess: "90%+",
    },
  },

  // Marketing Campaign Automation
  marketingCampaign: {
    id: "template-marketing-campaign-001",
    name: "Multi-Channel Marketing Automation",
    description:
      "End-to-end marketing campaign management across email, social media, and advertising platforms",
    category: "marketing",
    complexity: "high",
    estimatedSetupTime: "45-60 minutes",
    expectedMonthlyImpact: "25-40% increase in campaign ROI",
    tags: ["marketing", "automation", "social_media", "email", "analytics"],

    trigger: {
      type: "intent_match",
      intentCriteria: {
        primaryIntent: "launch_marketing_campaign",
        confidenceThreshold: 0.85,
        requiredEntities: ["campaign_name", "target_audience", "budget"],
      },
    },

    actions: [
      {
        type: "skill_execution",
        description: "Create campaign strategy and content plan",
        parameters: {
          skill: "marketingAutomationSkill.createCampaignPlan",
          channels: ["email", "social_media", "ads"],
          targetAudience: "auto_detect",
          budget: "specified_or_estimated",
        },
      },
      {
        type: "skill_execution",
        description: "Generate campaign content and creatives",
        parameters: {
          skill: "contentCreationSkill.generateCampaignAssets",
          formats: [
            "email_templates",
            "social_posts",
            "ad_copy",
            "landing_pages",
          ],
          brandGuidelines: "enforced",
        },
      },
      {
        type: "skill_execution",
        description: "Schedule and deploy across channels",
        parameters: {
          skill: "socialMediaSkill.schedulePosts",
          platforms: ["twitter", "linkedin", "facebook", "instagram"],
          optimalTiming: "auto_calculate",
        },
      },
      {
        type: "skill_execution",
        description: "Launch email campaign sequence",
        parameters: {
          skill: "marketingManagerSkills.executeEmailCampaign",
          segment: "target_audience",
          personalization: "dynamic",
        },
      },
      {
        type: "skill_execution",
        description: "Monitor and optimize performance",
        parameters: {
          skill: "dataAnalystSkill.trackCampaignMetrics",
          kpis: [
            "open_rate",
            "click_rate",
            "conversion_rate",
            "roi",
            "engagement",
          ],
        },
      },
      {
        type: "conditional_branch",
        description: "Auto-optimize based on performance",
        parameters: {
          condition: "conversion_rate < 2% OR roi < 100%",
          actionOnTrue: "adjust_targeting_or_budget",
          optimizationRules: "predefined_strategies",
        },
      },
      {
        type: "notification",
        description: "Send campaign performance report",
        parameters: {
          channels: ["slack", "email"],
          recipients: "marketing_team",
          frequency: "daily_during_campaign",
          format: "executive_summary",
        },
      },
    ],

    successMetrics: {
      conversionRate: "> 5%",
      roi: "> 200%",
      engagementRate: "> 15%",
      costPerAcquisition: "< $50",
    },
  },

  // Content Creation & Distribution
  contentCreation: {
    id: "template-content-creation-001",
    name: "Automated Content Production Pipeline",
    description:
      "End-to-end content creation, optimization, and distribution across multiple platforms",
    category: "content",
    complexity: "medium",
    estimatedSetupTime: "25-40 minutes",
    expectedMonthlyImpact: "50-75% increase in content output",
    tags: ["content", "creation", "seo", "distribution", "automation"],

    trigger: {
      type: "scheduled",
      schedule: "0 8 * * 1-5", // Weekdays at 8 AM
    },

    actions: [
      {
        type: "skill_execution",
        description: "Generate content ideas based on trends",
        parameters: {
          skill: "contentCreationSkill.generateIdeas",
          topics: "industry_relevant",
          trendAnalysis: "real_time",
          seoPotential: "high",
        },
      },
      {
        type: "skill_execution",
        description: "Create optimized content pieces",
        parameters: {
          skill: "contentCreationSkill.createContent",
          formats: ["blog_posts", "social_updates", "newsletters"],
          seoOptimization: "automatic",
          qualityStandards: "publish_ready",
        },
      },
      {
        type: "skill_execution",
        description: "Schedule for publication",
        parameters: {
          skill: "socialMediaSkill.scheduleContent",
          platforms: ["blog", "twitter", "linkedin", "newsletter"],
          optimalTiming: "audience_behavior_based",
        },
      },
      {
        type: "skill_execution",
        description: "Distribute to additional channels",
        parameters: {
          skill: "contentMarketerSkills.crossPost",
          syndication: "auto_approved_networks",
          canonicalLinks: "maintained",
        },
      },
      {
        type: "skill_execution",
        description: "Track performance and engagement",
        parameters: {
          skill: "dataAnalystSkill.analyzeContentPerformance",
          metrics: ["views", "shares", "comments", "backlinks", "seo_rankings"],
        },
      },
      {
        type: "conditional_branch",
        description: "Identify top performing content for repurposing",
        parameters: {
          condition: "engagement > 1000 OR conversions > 50",
          actionOnTrue: "repurpose_content",
          repurposingStrategies: ["video", "podcast", "infographic"],
        },
      },
    ],

    successMetrics: {
      contentOutput: "5-10 pieces weekly",
      engagementRate: "> 20%",
      seoRankings: "top 3 for target keywords",
      repurposingEfficiency: "80%+",
    },
  },

  // Financial Planning & Analysis
  financialPlanning: {
    id: "template-financial-planning-001",
    name: "Comprehensive Financial Planning Suite",
    description:
      "Automated financial analysis, budgeting, forecasting, and investment optimization",
    category: "finance",
    complexity: "high",
    estimatedSetupTime: "35-50 minutes",
    expectedMonthlyImpact: "15-25% improvement in financial efficiency",
    tags: ["finance", "budgeting", "forecasting", "investment", "analysis"],

    trigger: {
      type: "scheduled",
      schedule: "0 6 * * 1", // Every Monday at 6 AM
    },

    actions: [
      {
        type: "skill_execution",
        description: "Aggregate financial data from all sources",
        parameters: {
          skill: "financeSkillIndex.consolidateFinancialData",
          sources: [
            "bank_accounts",
            "investment_accounts",
            "credit_cards",
            "invoicing",
          ],
        },
      },
      {
        type: "skill_execution",
        description: "Generate comprehensive financial reports",
        parameters: {
          skill: "financialAnalystSkills.createFinancialStatements",
          reports: [
            "balance_sheet",
            "income_statement",
            "cash_flow",
            "budget_variance",
          ],
        },
      },
      {
        type: "skill_execution",
        description: "Perform investment portfolio analysis",
        parameters: {
          skill: "financeAgentSkills.analyzeInvestments",
          metrics: ["performance", "risk", "diversification", "fees"],
        },
      },
      {
        type: "skill_execution",
        description: "Create personalized financial recommendations",
        parameters: {
          skill: "financialGoalsSkill.generateRecommendations",
          areas: ["savings", "investments", "debt_management", "retirement"],
        },
      },
      {
        type: "skill_execution",
        description: "Generate tax optimization strategies",
        parameters: {
          skill: "taxExpertSkills.optimizeTaxStrategy",
          compliance: "fully_compliant",
          savingsPotential: "maximized",
        },
      },
      {
        type: "notification",
        description: "Deliver financial insights report",
        parameters: {
          channels: ["email", "mobile_app"],
          recipients: "user",
          format: "interactive_dashboard",
          actionableInsights: "highlighted",
        },
      },
      {
        type: "conditional_branch",
        description: "Alert for financial anomalies or opportunities",
        parameters: {
          condition: "spending_anomaly OR investment_opportunity",
          actionOnTrue: "immediate_alert",
          urgency: "real_time",
        },
      },
    ],

    successMetrics: {
      financialHealth: "improving_quarterly",
      investmentReturns: "beat_benchmark",
      taxSavings: "> 15%",
      budgetAdherence: "95%+",
    },
  },

  // Project Management Automation
  projectManagement: {
    id: "template-project-management-001",
    name: "Intelligent Project Coordination System",
    description:
      "End-to-end project management with automated task allocation, progress tracking, and team coordination",
    category: "project_management",
    complexity: "medium",
    estimatedSetupTime: "20-35 minutes",
    expectedMonthlyImpact: "30-45% improvement in project delivery time",
    tags: ["projects", "tasks", "team_collaboration", "timelines", "reporting"],

    trigger: {
      type: "intent_match",
      intentCriteria: {
        primaryIntent: "manage_project",
        confidenceThreshold: 0.75,
        requiredEntities: ["project_name", "team_members", "deadline"],
      },
    },

    actions: [
      {
        type: "skill_execution",
        description: "Create project plan and timeline",
        parameters: {
          skill: "projectManagerSkills.createProjectPlan",
          methodology: "agile_or_waterfall",
          dependencies: "auto_identified",
          criticalPath: "calculated",
        },
      },
      {
        type: "skill_execution",
        description: "Assign tasks to team members",
        parameters: {
          skill: "asanaSkills.assignTasks",
          allocation: "skill_based",
          workload: "balanced",
          preferences: "considered",
        },
      },
      {
        type: "skill_execution",
        description: "Set up collaboration channels",
        parameters: {
          skill: "platformRouter.setupProjectCommunications",
          tools: ["slack", "teams", "email", "document_sharing"],
        },
      },
      {
        type: "skill_execution",
        description: "Monitor progress and milestones",
        parameters: {
          skill: "projectManagerSkills.trackProgress",
          metrics: [
            "completion_rate",
            "timeline_adherence",
            "budget_utilization",
          ],
        },
      },
      {
        type: "skill_execution",
        description: "Generate status reports",
        parameters: {
          skill: "dataAnalystSkill.createProjectReports",
          frequency: "weekly",
          audience: "stakeholders",
          format: "executive_summary",
        },
      },
      {
        type: "conditional_branch",
        description: "Handle project risks and issues",
        parameters: {
          condition: "timeline_slippage OR budget_overrun",
          actionOnTrue: "risk_mitigation",
          escalation: "auto_triggered",
        },
      },
      {
        type: "notification",
        description: "Send team updates and reminders",
        parameters: {
          channels: ["slack", "email", "mobile_push"],
          recipients: "project_team",
          frequency: "daily_standup",
          content: "progress_updates",
        },
      },
    ],

    successMetrics: {
      onTimeDelivery: "90%+",
      budgetAdherence: "95%+",
      teamSatisfaction: "measured_quarterly",
      qualityScore: "4.5/5+",
    },
  },

  // Content & File Management Automation
  contentFileManagement: {
    id: "template-content-file-management-001",
    name: "Auto-Archive & Task Linker",
    description:
      "Automatically archive, tag, and link new files from cloud storage (Drive/Dropbox) to related tasks in Asana or Trello with Slack notifications.",
    category: "data_management",
    complexity: "medium",
    estimatedSetupTime: "15-25 minutes",
    expectedMonthlyImpact: "15-20% reduction in document retrieval time",
    tags: ["google_drive", "dropbox", "asana", "trello", "slack", "automation"],

    trigger: {
      type: "integration_event",
      integrationId: "google_drive",
      eventType: "new_file_uploaded",
      parameters: {
        monitorFolders: ["auto_detect", "specific_folders"],
        fileTypes: ["all", "documents", "images", "pdfs"],
      },
    },

    actions: [
      {
        type: "skill_execution",
        description: "Analyze file content and extract context",
        parameters: {
          skill: "aiVisionSkill.analyzeDocument",
          extractionFields: ["project_name", "task_id", "keywords", "importance"],
          context: "cross_integration_mapping",
        },
      },
      {
        type: "skill_execution",
        description: "Identify and link to related tasks",
        parameters: {
          skill: "taskManagerSkills.linkFileToTask",
          platforms: ["asana", "trello", "jira"],
          matchCriteria: ["filename_pattern", "content_context", "metadata"],
          autoLinkConfidence: 0.8,
        },
      },
      {
        type: "skill_execution",
        description: "Organize and archive file in cloud storage",
        parameters: {
          skill: "fileSystemSkills.organizeFile",
          targetPath: "/Archive/{{project_name}}/{{year}}/{{month}}",
          tagging: ["auto_generated_tags", "process_labels"],
        },
      },
      {
        type: "notification",
        description: "Notify team of new file link",
        parameters: {
          channels: ["slack"],
          recipients: "project_channel",
          messageTemplate: "file_archived_and_linked",
          includePreview: true,
        },
      },
    ],

    successMetrics: {
      fileLinkAccuracy: "95%+",
      archivingSpeed: "< 5 minutes",
      searchEfficiency: "improved by 40%",
      teamAwareness: "100% notification rate",
    },
  },
  burnoutProtection: {
    id: "template-burnout-protection-001",
    name: "Burnout & Overload Protection",
    description: "Proactively monitor workload and suggest focus blocks, meeting rescheduling, and delegation.",
    category: "wellness",
    trigger: {
      type: "scheduled",
      schedule: "0 9 * * 1", // Every Monday morning
    },
    actions: [
      {
        type: "skill_execution",
        description: "Analyze current burnout risk",
        parameters: {
          skill: "wellnessSkill.getCurrentRisk",
        },
      },
      {
        type: "conditional_branch",
        condition: "risk_level == 'High' || risk_level == 'Critical'",
        actions: [
          {
            type: "skill_execution",
            description: "Generate focus block suggestions",
            parameters: {
              skill: "wellnessSkill.suggestFocusBlocks",
            },
          },
          {
            type: "notification",
            channel: "slack",
            message: "⚠️ High burnout risk detected. I've prepared some focus block suggestions for you.",
          },
        ],
      },
    ],
    successMetrics: {
      weeklyFocusHours: "> 10 hours",
      stressLevelReduction: "20%",
    },
  },
  autoScheduleConflictResolution: {
    id: "template-schedule-conflict-resolution-001",
    name: "Auto Schedule Conflict Resolution",
    description: "Detect and automatically resolve calendar conflicts by finding the best available gaps.",
    category: "scheduling",
    trigger: {
      type: "event",
      event: "scheduling_conflict_detected",
    },
    actions: [
      {
        type: "skill_execution",
        description: "Fetch schedule optimizations",
        parameters: {
          skill: "schedulingSkill.getOptimizations",
        },
      },
      {
        type: "skill_execution",
        description: "Check stakeholder opinions based on roles",
        parameters: {
          skill: "schedulingSkill.getAttendeeOpinionByRole",
          role: "decision_maker",
        },
        condition: "optimizations.length > 0",
      },
      {
        type: "conditional_branch",
        condition: "optimizations.length > 0 && stakeholderOpinion.approved",
        actions: [
          {
            type: "skill_execution",
            description: "Automatically resolve conflicts and notify attendees",
            parameters: {
              skill: "schedulingSkill.autoResolveConflicts",
            },
          },
          {
            type: "skill_execution",
            description: "Initiate follow-up meeting if necessary",
            parameters: {
              skill: "schedulingSkill.initiateNewMeeting",
              title: "Draft Sync: Conflict Follow-up",
              durationMinutes: 30,
            },
            condition: "resolutionSucceeded && requiresFollowUp",
          },
          {
            type: "notification",
            channel: "slack",
            message: "📅 Resolved schedule conflicts and updated all participants. New slots have been secured and notifications sent.",
          },
        ],
      },
    ],
    successMetrics: {
      conflictResolutionRate: "100%",
      manualCleanupTimeReduced: "30 min/week",
    },
  },
};
