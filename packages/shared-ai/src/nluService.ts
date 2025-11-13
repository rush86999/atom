import { OpenAIService } from "./openaiService";
import { WorkflowService } from "./workflowService";
import { SkillService } from "./skillService";
import { NLULeadAgent } from "../nlu_agents/nlu_lead_agent";
import { RealLLMService } from "../lib/llmUtils";
import * as fs from "fs";
import * as path from "path";

export interface CrossPlatformIntent {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  action: string;
  parameters: Record<string, any>;
  workflow?: string;
  requiresConfirmation?: boolean;
  suggestedResponses?: string[];
  context?: Record<string, any>;
  platforms: string[]; // Target platforms for this intent
  crossPlatformAction?: boolean;
  dataIntegration?: DataIntegrationPlan;
}

export interface DataIntegrationPlan {
  sourcePlatforms: string[];
  targetPlatforms: string[];
  syncOperation: 'create' | 'update' | 'delete' | 'read' | 'sync';
  entityMapping: Record<string, string>;
  transformationRules: Array<{
    source: string;
    target: string;
    operation: string;
  }>;
}

export interface ConversationContext {
  userId: string;
  sessionId: string;
  previousIntents: string[];
  entities: Record<string, any>;
  workflowState?: any;
  timestamp: Date;
  platformContext?: Record<string, any>; // Platform-specific context
  crossPlatformHistory?: Array<{
    platform: string;
    action: string;
    timestamp: Date;
    result: any;
  }>;
  userPreferences?: {
    preferredPlatforms: Record<string, string>;
    automationLevel: 'manual' | 'semi-auto' | 'full-auto';
    integrationPatterns: string[];
  };
}

export interface IntentDefinition {
  name: string;
  description: string;
  patterns: string[];
  examples: string[];
  entities: string[];
  action: string;
  workflow?: string;
  requiresConfirmation?: boolean;
  confirmationPhrases?: string[];
  platforms?: string[]; // Target platforms for this intent
  crossPlatform?: boolean; // Whether this intent spans multiple platforms
  dataIntegration?: DataIntegrationPlan;
}

export interface AIInsight {
  type: 'pattern' | 'recommendation' | 'prediction' | 'optimization';
  confidence: number;
  description: string;
  suggestedAction?: string;
  platforms?: string[];
  estimatedImpact?: string;
}

export interface NLUMetrics {
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageProcessingTime: number;
  intentDistribution: Record<string, number>;
  serviceUsage: Record<string, number>;
  lastRequestTime: Date | null;
  crossPlatformSuccess: number;
  automationPrevented: number;
  userSatisfactionScore: number;
  aiInsightsGenerated: number;
}

export class NLUService {
  private openaiService: OpenAIService;
  private workflowService: WorkflowService;
  private skillService: SkillService;
  private intentDefinitions: IntentDefinition[];
  private aiInsights: AIInsight[] = [];

  private configPath: string;
  private metrics: NLUMetrics;
  private trainingExamples: Array<{
    message: string;
    intent: string;
    entities: Record<string, any>;
    timestamp: Date;
    platforms?: string[];
    crossPlatform?: boolean;
  }>;
  private leadAgent: NLULeadAgent | null;
  private platformIntegrations: Map<string, any> = new Map();
  private dataIntegrations: Map<string, DataIntegrationPlan> = new Map();

  // Production optimization properties
  private performanceCache: Map<string, NLUResponse> = new Map();
  private patternCache: Map<string, IntentDefinition[]> = new Map();
  private userLearningProfiles: Map<string, any> = new Map();

  constructor(configPath?: string) {
    this.openaiService = new OpenAIService();
    this.workflowService = new WorkflowService();
    this.skillService = new SkillService();
    this.configPath =
      configPath || path.join(__dirname, "..", "..", "config", "intents.json");
    this.intentDefinitions = this.loadIntentDefinitions();
    this.metrics = {
      totalRequests: 0,
      successfulRequests: 0,
      failedRequests: 0,
      averageProcessingTime: 0,
      intentDistribution: {},
      serviceUsage: {},
      lastRequestTime: null,
      crossPlatformSuccess: 0,
      automationPrevented: 0,
      userSatisfactionScore: 0,
      aiInsightsGenerated: 0,
    };
    this.trainingExamples = [];
    this.loadTrainingExamples();
    this.leadAgent = null;
    this.initializePlatformIntegrations();
    this.initializeDataIntegrations();
  }

  private initializePlatformIntegrations(): void {
    // Initialize cross-platform integration mappings
    const platformMappings = {
      'asana': ['task_management', 'project_tracking'],
      'slack': ['communication', 'notifications'],
      'google_drive': ['document_storage', 'file_sharing'],
      'gmail': ['email', 'communication'],
      'calendar': ['scheduling', 'events'],
      'zendesk': ['customer_support', 'ticketing'],
      'hubspot': ['crm', 'marketing'],
      'salesforce': ['crm', 'sales'],
      'notion': ['documentation', 'knowledge_base'],
      'github': ['development', 'version_control'],
      'figma': ['design', 'collaboration'],
      'discord': ['communication', 'community'],
      'teams': ['communication', 'meetings'],
      'trello': ['task_management', 'kanban'],
      'jira': ['issue_tracking', 'project_management'],
      'monday': ['project_management', 'workflows'],
      'airtable': ['database', 'spreadsheets'],
      'box': ['document_storage', 'file_sharing'],
      'dropbox': ['file_storage', 'sync'],
      'onedrive': ['document_storage', 'collaboration'],
      'sharepoint': ['document_management', 'enterprise'],
      'zoom': ['meetings', 'video_conferencing'],
      'stripe': ['payments', 'billing'],
      'plaid': ['banking', 'financial_data'],
      'xero': ['accounting', 'financial'],
      'quickbooks': ['accounting', 'invoicing'],
      'shopify': ['ecommerce', 'inventory'],
      'gitlab': ['development', 'ci_cd'],
      'linear': ['issue_tracking', 'development'],
      'bamboohr': ['hr', 'employee_management'],
      'vscode': ['development', 'coding'],
      'tableau': ['analytics', 'visualization'],
      'nextjs': ['development', 'web_framework'],
    };

    for (const [platform, capabilities] of Object.entries(platformMappings)) {
      this.platformIntegrations.set(platform, {
        name: platform,
        capabilities,
        connected: false,
        lastSync: null,
        availableActions: this.getPlatformActions(platform),
      });
    }
  }

  private initializeDataIntegrations(): void {
    // Initialize common cross-platform integration patterns
    const integrationPatterns: DataIntegrationPlan[] = [
      {
        sourcePlatforms: ['gmail', 'slack'],
        targetPlatforms: ['asana', 'trello'],
        syncOperation: 'create',
        entityMapping: {
          'email_subject': 'task_name',
          'email_body': 'task_description',
          'sender': 'assignee',
          'priority': 'priority',
        },
        transformationRules: [
          {
            source: 'email_contains_action_items',
            target: 'create_task_with_assignee',
            operation: 'extract_action_items',
          },
        ],
      },
      {
        sourcePlatforms: ['calendar', 'zoom'],
        targetPlatforms: ['slack', 'teams'],
        syncOperation: 'create',
        entityMapping: {
          'event_title': 'message_content',
          'start_time': 'reminder_time',
          'attendees': 'mention_users',
        },
        transformationRules: [
          {
            source: 'meeting_scheduled',
            target: 'send_reminder',
            operation: 'create_meeting_reminder',
          },
        ],
      },
      {
        sourcePlatforms: ['github', 'gitlab'],
        targetPlatforms: ['slack', 'teams'],
        syncOperation: 'update',
        entityMapping: {
          'commit_message': 'message_content',
          'author': 'user',
          'branch': 'project',
        },
        transformationRules: [
          {
            source: 'code_committed',
            target: 'notification',
            operation: 'create_commit_notification',
          },
        ],
      },
    ];

    for (const pattern of integrationPatterns) {
      const key = pattern.sourcePlatforms.join('-') + '-to-' + pattern.targetPlatforms.join('-');
      this.dataIntegrations.set(key, pattern);
    }
  }

  private getPlatformActions(platform: string): string[] {
    const actionMap: Record<string, string[]> = {
      'asana': ['create_task', 'update_task', 'assign_task', 'comment_task'],
      'slack': ['send_message', 'create_channel', 'invite_user', 'set_status'],
      'google_drive': ['upload_file', 'share_file', 'create_folder', 'search_docs'],
      'gmail': ['send_email', 'search_emails', 'create_draft', 'label_email'],
      'calendar': ['create_event', 'update_event', 'invite_attendees', 'schedule_meeting'],
      'zendesk': ['create_ticket', 'update_ticket', 'reply_ticket', 'escalate_ticket'],
      'hubspot': ['create_contact', 'update_deal', 'log_activity', 'create_campaign'],
      // Add more platform actions as needed
    };
    return actionMap[platform] || [];
  }

  private loadTrainingExamples(): void {
    const trainingPath = path.join(
      path.dirname(this.configPath),
      "training-examples.json",
    );

    try {
      if (fs.existsSync(trainingPath)) {
        const content = fs.readFileSync(trainingPath, "utf-8");
        const data = JSON.parse(content);
        if (data.examples && Array.isArray(data.examples)) {
          this.trainingExamples = data.examples.map((ex: any) => ({
            ...ex,
            timestamp: new Date(ex.timestamp),
          }));
          console.log(
            `Loaded ${this.trainingExamples.length} training examples`,
          );
        }
      }
    } catch (error) {
      console.warn("Failed to load training examples:", error);
    }
  }

  private saveTrainingExamples(): void {
    const trainingPath = path.join(
      path.dirname(this.configPath),
      "training-examples.json",
    );

    try {
      const data = {
        version: "1.0.0",
        lastUpdated: new Date().toISOString(),
        examples: this.trainingExamples.map((ex) => ({
          ...ex,
          timestamp: ex.timestamp.toISOString(),
        })),
      };

      fs.writeFileSync(trainingPath, JSON.stringify(data, null, 2));
    } catch (error) {
      console.error("Failed to save training examples:", error);
    }
  }

  private loadIntentDefinitions(): IntentDefinition[] {
    try {
      // Try to load from external config file first
      if (fs.existsSync(this.configPath)) {
        const configContent = fs.readFileSync(this.configPath, "utf-8");
        const config = JSON.parse(configContent);

        if (config.intents && Array.isArray(config.intents)) {
          console.log(
            `Loaded ${config.intents.length} intents from config file`,
          );
          return config.intents;
        }
      }
    } catch (error) {
      console.warn(
        "Failed to load intents from config file, using defaults:",
        error,
      );
    }

    // Fallback to default intents
    return this.getDefaultIntentDefinitions();
  }

  private getDefaultIntentDefinitions(): IntentDefinition[] {
    return [
      {
        name: "create_task",
        description: "Create a new task in a project management system",
        patterns: [
          "create a task",
          "add task",
          "new task",
          "create task for",
          "add to my tasks",
          "create todo",
          "add todo item",
        ],
        examples: [
          "Create a task to finish the report",
          "Add a task for meeting preparation",
          "New task: Review PR #123",
        ],
        entities: ["task_name", "project", "due_date", "priority"],
        action: "create_task",
        workflow: "task_creation",
      },
      {
        name: "schedule_meeting",
        description: "Schedule a meeting or calendar event",
        patterns: [
          "schedule meeting",
          "set up meeting",
          "create meeting",
          "book meeting",
          "schedule call",
          "set up call",
        ],
        examples: [
          "Schedule a meeting with John tomorrow at 2pm",
          "Set up a team meeting for Friday",
          "Book a 30-minute call with Sarah",
        ],
        entities: ["participants", "date", "time", "duration", "topic"],
        action: "schedule_meeting",
        workflow: "meeting_scheduling",
      },
      {
        name: "search_information",
        description: "Search for information or documents",
        patterns: [
          "search for",
          "find",
          "look up",
          "where is",
          "show me",
          "get information about",
          "search documents",
        ],
        examples: [
          "Search for project documentation",
          "Find the sales report from last quarter",
          "Look up customer information for ABC Corp",
        ],
        entities: ["search_query", "document_type", "time_period"],
        action: "search",
        workflow: "information_retrieval",
      },
      {
        name: "analyze_data",
        description: "Analyze data or generate reports",
        patterns: [
          "analyze",
          "generate report",
          "create dashboard",
          "show analytics",
          "data analysis",
          "performance report",
        ],
        examples: [
          "Analyze sales data for Q3",
          "Generate a performance report",
          "Show me analytics for the website",
        ],
        entities: ["data_type", "time_period", "metrics"],
        action: "analyze_data",
        workflow: "data_analysis",
      },
      {
        name: "integrate_service",
        description: "Connect or integrate with external services",
        patterns: [
          "connect to",
          "integrate with",
          "link",
          "set up integration",
          "connect google drive",
          "integrate slack",
        ],
        examples: [
          "Connect to my Google Drive",
          "Integrate with Slack",
          "Set up Dropbox integration",
        ],
        entities: ["service_name", "connection_type"],
        action: "integrate_service",
        requiresConfirmation: true,
      },
      {
        name: "execute_workflow",
        description: "Execute a specific workflow or automation",
        patterns: [
          "run workflow",
          "execute workflow",
          "start automation",
          "trigger workflow",
          "run the",
          "execute the",
        ],
        examples: [
          "Run the daily report workflow",
          "Execute the customer onboarding automation",
          "Trigger the data sync workflow",
        ],
        entities: ["workflow_name", "parameters"],
        action: "execute_workflow",
        workflow: "workflow_execution",
      },
    ];
  }

  // Enhanced cross-platform AI methods
  async understandCrossPlatformMessage(
    message: string,
    context?: ConversationContext,
    options?: {
      service?: "openai" | "rules" | "hybrid";
      apiKey?: string;
      platforms?: string[];
    },
  ): Promise<CrossPlatformIntent> {
    const startTime = Date.now();
    this.metrics.totalRequests++;

    try {
      // Check cache first for performance
      const cacheKey = `${message}_${JSON.stringify(context || {})}_${JSON.stringify(options || {})}`;
      if (this.performanceCache.has(cacheKey)) {
        const cached = this.performanceCache.get(cacheKey)!;
        console.log(`Cache hit for cross-platform intent: ${cached.intent}`);
        return cached;
      }

      // Enhanced intent detection with cross-platform awareness
      let response: CrossPlatformIntent;

      switch (options?.service || "hybrid") {
        case "openai":
          response = await this.understandCrossPlatformWithAI(message, context, options);
          break;
        case "rules":
          response = this.understandCrossPlatformWithRules(message, context);
          break;
        case "hybrid":
        default:
          response = await this.understandCrossPlatformHybrid(message, context, options);
          break;
      }

      // Add AI insights for user recommendations
      const insights = await this.generateAIInsights(message, response, context);
      response.suggestedResponses = insights.map(i => i.description);

      // Cache response for performance
      this.performanceCache.set(cacheKey, response);

      // Update metrics
      const processingTime = Date.now() - startTime;
      this.updateMetrics(response, processingTime, true);

      return response;
    } catch (error) {
      console.error("Cross-platform NLU processing error:", error);
      this.metrics.failedRequests++;
      return this.getCrossPlatformFallbackResponse(message);
    }
  }

  private async understandCrossPlatformWithAI(
    message: string,
    context?: ConversationContext,
    options?: { apiKey?: string },
  ): Promise<CrossPlatformIntent> {
    // Build enhanced prompt for cross-platform understanding
    const platformContext = context?.platformContext || {};
    const userPreferences = context?.userPreferences || {};
    
    const prompt = `
You are a cross-platform AI assistant for ATOM platform. You must understand user intent across multiple integrated platforms.

AVAILABLE PLATFORMS:
${Array.from(this.platformIntegrations.entries()).map(([name, info]) => 
  `- ${name}: ${info.capabilities.join(', ')}`
).join('\n')}

CROSS-PLATFORM INTEGRATIONS:
${Array.from(this.dataIntegrations.entries()).map(([key, plan]) => 
  `- ${key}: ${plan.sourcePlatforms.join(' → ')} ${plan.syncOperation} ${plan.targetPlatforms.join(' & ')}`
).join('\n')}

USER PREFERENCES:
${JSON.stringify(userPreferences, null, 2)}

PREVIOUS CONTEXT:
${JSON.stringify(platformContext, null, 2)}

USER MESSAGE: "${message}"

RESPOND WITH JSON:
{
  "intent": "intent_name",
  "confidence": 0.95,
  "entities": {"extracted": "entities"},
  "action": "action_to_take",
  "parameters": {"action": "parameters"},
  "platforms": ["target", "platforms"],
  "crossPlatformAction": true,
  "dataIntegration": {
    "sourcePlatforms": ["source", "platforms"],
    "targetPlatforms": ["target", "platforms"],
    "syncOperation": "create|update|delete|read|sync",
    "entityMapping": {"source": "target"}
  },
  "requiresConfirmation": false
}
    `;

    try {
      const openaiResponse = await this.openaiService.generateCompletion({
        prompt,
        maxTokens: 1000,
        temperature: 0.3,
      });

      const aiResult = JSON.parse(openaiResponse.content);
      
      return {
        ...aiResult,
        suggestedResponses: this.generateSuggestedResponses(aiResult.intent, aiResult.entities),
        context: {
          ...platformContext,
          aiProcessed: true,
          crossPlatformAnalysis: true,
        },
      };
    } catch (error) {
      console.error("Cross-platform AI understanding failed:", error);
      throw error;
    }
  }

  private understandCrossPlatformWithRules(
    message: string,
    context?: ConversationContext,
  ): CrossPlatformIntent {
    const lowerMessage = message.toLowerCase();
    
    // Enhanced rule-based matching with cross-platform patterns
    for (const intent of this.intentDefinitions) {
      if (intent.crossPlatform && intent.platforms) {
        for (const pattern of intent.patterns) {
          if (lowerMessage.includes(pattern.toLowerCase())) {
            const entities = this.extractCrossPlatformEntities(lowerMessage, intent);
            
            return {
              intent: intent.name,
              confidence: 0.85,
              entities,
              action: intent.action,
              parameters: entities,
              workflow: intent.workflow,
              platforms: intent.platforms,
              crossPlatformAction: true,
              dataIntegration: intent.dataIntegration,
              requiresConfirmation: intent.requiresConfirmation || false,
              suggestedResponses: this.generateCrossPlatformResponses(intent.name, entities),
              context: {
                ...context?.platformContext,
                ruleMatched: true,
                pattern: pattern,
              },
            };
          }
        }
      }
    }

    // Fallback to basic intent understanding
    const basicResponse = this.understandWithRules(message, context);
    return {
      ...basicResponse,
      platforms: this.detectRelevantPlatforms(lowerMessage),
      crossPlatformAction: this.isCrossPlatformRequest(lowerMessage),
    };
  }

  private async understandCrossPlatformHybrid(
    message: string,
    context?: ConversationContext,
    options?: { apiKey?: string },
  ): Promise<CrossPlatformIntent> {
    // Combine AI and rule-based approaches for best accuracy
    
    const ruleResponse = this.understandCrossPlatformWithRules(message, context);
    
    // If high confidence rule match, use it
    if (ruleResponse.confidence > 0.9) {
      ruleResponse.context = {
        ...ruleResponse.context,
        hybridMethod: 'rules_priority',
      };
      return ruleResponse;
    }

    // Otherwise, use AI for complex understanding
    try {
      const aiResponse = await this.understandCrossPlatformWithAI(message, context, options);
      
      // Merge AI and rule results
      const hybridResponse: CrossPlatformIntent = {
        ...aiResponse,
        entities: {
          ...ruleResponse.entities,
          ...aiResponse.entities,
        },
        platforms: [
          ...new Set([
            ...(ruleResponse.platforms || []),
            ...(aiResponse.platforms || [])
          ])
        ],
        context: {
          ...aiResponse.context,
          ...ruleResponse.context,
          hybridMethod: 'ai_enhanced',
        },
      };

      return hybridResponse;
    } catch (error) {
      console.warn("AI method failed, using rules:", error);
      ruleResponse.context = {
        ...ruleResponse.context,
        hybridMethod: 'rules_fallback',
      };
      return ruleResponse;
    }
  }

  private extractCrossPlatformEntities(
    message: string,
    intent: IntentDefinition,
  ): Record<string, any> {
    const entities: Record<string, any> = {};

    // Extract platform mentions
    const platformNames = Array.from(this.platformIntegrations.keys());
    for (const platform of platformNames) {
      if (message.includes(platform)) {
        entities.platforms = entities.platforms || [];
        entities.platforms.push(platform);
      }
    }

    // Extract cross-platform indicators
    const crossPlatformKeywords = ['all platforms', 'everywhere', 'sync', 'across', 'all tools', 'cross-platform'];
    for (const keyword of crossPlatformKeywords) {
      if (message.includes(keyword)) {
        entities.crossPlatform = true;
        break;
      }
    }

    // Extract standard entities
    for (const entity of intent.entities) {
      const value = this.extractEntity(message, entity);
      if (value) {
        entities[entity] = value;
      }
    }

    return entities;
  }

  private generateCrossPlatformResponses(
    intent: string,
    entities: Record<string, any>,
  ): string[] {
    const platforms = entities.platforms || [];
    const responses: string[] = [];

    switch (intent) {
      case "create_cross_platform_task":
        if (platforms.length > 0) {
          responses.push(`✅ Task will be created in ${platforms.join(' & ')}`);
          responses.push(`🔄 Syncing task across ${platforms.length} platforms`);
        } else {
          responses.push(`📋 Create task in all connected platforms?`);
        }
        break;
        
      case "cross_platform_search":
        responses.push(`🔍 Searching across all connected platforms...`);
        responses.push(`📊 Unified search results will be compiled`);
        break;
        
      case "automated_workflow_trigger":
        responses.push(`⚡ Creating cross-platform automation rule...`);
        responses.push(`🤖 Workflow will trigger automatically when conditions are met`);
        break;
        
      default:
        responses.push(`🚀 Executing cross-platform action...`);
        responses.push(`📱 Results will be synchronized across all platforms`);
        break;
    }

    return responses;
  }

  private async generateAIInsights(
    message: string,
    intent: CrossPlatformIntent,
    context?: ConversationContext,
  ): Promise<AIInsight[]> {
    const insights: AIInsight[] = [];

    // Pattern-based insights
    const userHistory = context?.crossPlatformHistory || [];
    if (userHistory.length > 5) {
      insights.push({
        type: 'pattern',
        confidence: 0.8,
        description: `I notice you frequently create cross-platform tasks. Would you like me to suggest a recurring automation?`,
        suggestedAction: 'Create automation template',
        estimatedImpact: 'Save 10-15 minutes per week',
      });
    }

    // Platform optimization insights
    if (intent.platforms && intent.platforms.length > 2) {
      insights.push({
        type: 'optimization',
        confidence: 0.9,
        description: `Consider creating a unified workspace template for your ${intent.platforms.length} most-used platforms`,
        suggestedAction: 'Set up workspace template',
        estimatedImpact: 'Reduce context switching by 60%',
      });
    }

    // Predictive insights
    if (intent.intent === 'create_cross_platform_task' && userHistory.some(h => h.action === 'create_cross_platform_task')) {
      insights.push({
        type: 'prediction',
        confidence: 0.75,
        description: `Based on your activity, you might want to create similar tasks tomorrow at 9am`,
        platforms: intent.platforms,
        suggestedAction: 'Schedule recurring task creation',
      });
    }

    this.metrics.aiInsightsGenerated += insights.length;
    this.aiInsights.push(...insights);

    return insights;
  }

  private detectRelevantPlatforms(message: string): string[] {
    const platforms: string[] = [];
    const lowerMessage = message.toLowerCase();

    for (const [platform, info] of this.platformIntegrations.entries()) {
      if (lowerMessage.includes(platform) || 
          info.capabilities.some(cap => lowerMessage.includes(cap))) {
        platforms.push(platform);
      }
    }

    return platforms.length > 0 ? platforms : ['all'];
  }

  private isCrossPlatformRequest(message: string): boolean {
    const crossPlatformKeywords = [
      'all platforms', 'everywhere', 'sync', 'across', 'all tools', 
      'cross-platform', 'in all', 'each platform', 'multiple'
    ];
    
    const lowerMessage = message.toLowerCase();
    return crossPlatformKeywords.some(keyword => lowerMessage.includes(keyword));
  }

  private updateMetrics(
    response: CrossPlatformIntent,
    processingTime: number,
    success: boolean,
  ): void {
    if (success) {
      this.metrics.successfulRequests++;
      this.metrics.averageProcessingTime = 
        (this.metrics.averageProcessingTime * (this.metrics.successfulRequests - 1) + processingTime) /
        this.metrics.successfulRequests;
      
      this.metrics.intentDistribution[response.intent] = 
        (this.metrics.intentDistribution[response.intent] || 0) + 1;
      
      if (response.crossPlatformAction) {
        this.metrics.crossPlatformSuccess++;
      }
    } else {
      this.metrics.failedRequests++;
    }
    
    this.metrics.lastRequestTime = new Date();
  }

  private getCrossPlatformFallbackResponse(message: string): CrossPlatformIntent {
    return {
      intent: "unknown",
      confidence: 0.1,
      entities: {},
      action: "fallback",
      parameters: {},
      platforms: [],
      crossPlatformAction: false,
      suggestedResponses: [
        "I'm not sure how to process this cross-platform request.",
        "Could you specify which platforms you'd like to work with?",
        "I can help with tasks across Asana, Slack, Google Drive, and more.",
      ],
      context: { fallback: true },
    };
  }

  async understandMessage(
    message: string,
    context?: ConversationContext,
    options?: {
      service?: "openai" | "rules" | "hybrid";
      apiKey?: string;
    },
  ): Promise<NLUResponse> {
    const service = options?.service || "hybrid";
    const startTime = Date.now();
    this.metrics.totalRequests++;
    this.metrics.serviceUsage[service] =
      (this.metrics.serviceUsage[service] || 0) + 1;

    try {
      let response: NLUResponse;

      switch (service) {
        case "openai":
          response = await this.understandWithOpenAI(message, context, options);
          break;
        case "rules":
          response = this.understandWithRules(message, context);
          break;
        case "hybrid":
        default:
          response = await this.understandHybrid(message, context, options);
          break;
      }

      // Enrich with workflow information if applicable
      if (response.workflow) {
        const workflowInfo = await this.workflowService.getWorkflowInfo(
          response.workflow,
        );
        response = { ...response, ...workflowInfo };
      }

      // Update metrics
      const processingTime = Date.now() - startTime;
      this.metrics.successfulRequests++;
      this.metrics.averageProcessingTime =
        (this.metrics.averageProcessingTime *
          (this.metrics.successfulRequests - 1) +
          processingTime) /
        this.metrics.successfulRequests;
      this.metrics.intentDistribution[response.intent] =
        (this.metrics.intentDistribution[response.intent] || 0) + 1;
      this.metrics.lastRequestTime = new Date();

      return response;
    } catch (error) {
      console.error("NLU processing error:", error);
      this.metrics.failedRequests++;
      this.metrics.lastRequestTime = new Date();
      return this.getFallbackResponse(message);
    }
  }

  private async understandWithOpenAI(
    message: string,
    context?: ConversationContext,
    options?: { apiKey?: string },
  ): Promise<NLUResponse> {
    const prompt = this.buildOpenAIPrompt(message, context);

    const messages = [
      {
        role: "system",
        content: prompt.system,
      },
      {
        role: "user",
        content: prompt.user,
      },
    ];

    const response = await this.openaiService.chatCompletion(messages, {
      model: "gpt-4",
      temperature: 0.1,
      maxTokens: 500,
    });

    return this.parseOpenAIResponse(response.content);
  }

  private understandWithRules(
    message: string,
    context?: ConversationContext,
  ): NLUResponse {
    const lowerMessage = message.toLowerCase();

    // Simple pattern matching
    for (const intent of this.intentDefinitions) {
      for (const pattern of intent.patterns) {
        if (lowerMessage.includes(pattern.toLowerCase())) {
          const entities = this.extractEntities(message, intent.entities);

          return {
            intent: intent.name,
            confidence: 0.7,
            entities,
            action: intent.action,
            parameters: entities,
            workflow: intent.workflow,
            requiresConfirmation: intent.requiresConfirmation,
            suggestedResponses: intent.confirmationPhrases,
          };
        }
      }
    }

    // Fallback to generic response
    return this.getFallbackResponse(message);
  }

  private async understandHybrid(
    message: string,
    context?: ConversationContext,
    options?: { apiKey?: string },
  ): Promise<NLUResponse> {
    // First try rules-based for speed
    const rulesResponse = this.understandWithRules(message, context);
    if (rulesResponse.confidence > 0.8) {
      return rulesResponse;
    }

    try {
      // Try using the lead agent with specialized agents for complex understanding
      const leadAgentResponse = await this.understandWithLeadAgent(
        message,
        context,
        options,
      );
      return leadAgentResponse;
    } catch (error) {
      console.warn("Lead agent failed, falling back to OpenAI:", error);
      // Fall back to simple AI for complex understanding
      return this.understandWithOpenAI(message, context, options);
    }
  }

  private buildOpenAIPrompt(
    message: string,
    context?: ConversationContext,
  ): {
    system: string;
    user: string;
  } {
    const intentsList = this.intentDefinitions
      .map(
        (intent) =>
          `- ${intent.name}: ${intent.description} (examples: ${intent.examples.slice(0, 2).join(", ")})`,
      )
      .join("\n");

    return {
      system: `You are an NLU system that understands user messages and extracts intents and entities.

Available intents:
${intentsList}

Respond with a JSON object containing:
- intent: the detected intent name
- confidence: confidence score 0-1
- entities: object with extracted entities
- action: the action to take
- parameters: parameters for the action
- workflow: optional workflow name
- requiresConfirmation: boolean if confirmation needed
- suggestedResponses: array of response suggestions

Context: ${context ? JSON.stringify(context) : "none"}

Respond only with valid JSON.`,
      user: `Message: "${message}"`,
    };
  }

  private parseOpenAIResponse(response: string): NLUResponse {
    try {
      const parsed = JSON.parse(response);
      return {
        intent: parsed.intent || "unknown",
        confidence: parsed.confidence || 0.5,
        entities: parsed.entities || {},
        action: parsed.action || "respond",
        parameters: parsed.parameters || {},
        workflow: parsed.workflow,
        requiresConfirmation: parsed.requiresConfirmation || false,
        suggestedResponses: parsed.suggestedResponses || [],
        context: parsed.context,
      };
    } catch (error) {
      console.error("Failed to parse OpenAI response:", error);
      return this.getFallbackResponse("");
    }
  }

  private extractEntities(
    message: string,
    entityTypes: string[],
  ): Record<string, any> {
    const entities: Record<string, any> = {};

    // Enhanced entity extraction with better pattern matching
    for (const entityType of entityTypes) {
      switch (entityType) {
        case "task_name":
          entities.task_name = this.extractTaskName(message);
          break;
        case "due_date":
          entities.due_date = this.extractDate(message);
          break;
        case "participants":
          entities.participants = this.extractParticipants(message);
          break;
        case "time":
          entities.time = this.extractTime(message);
          break;
        case "project":
          entities.project = this.extractProject(message);
          break;
        case "priority":
          entities.priority = this.extractPriority(message);
          break;
        case "search_query":
          entities.search_query = this.extractSearchQuery(message);
          break;
        case "document_type":
          entities.document_type = this.extractDocumentType(message);
          break;
        case "service_name":
          entities.service_name = this.extractServiceName(message);
          break;
        case "workflow_name":
          entities.workflow_name = this.extractWorkflowName(message);
          break;
        case "time_period":
          entities.time_period = this.extractTimePeriod(message);
          break;
        // Add more entity extractors as needed
      }
    }

    return entities;
  }

  private extractTaskName(message: string): string {
    // Enhanced task name extraction with better pattern matching
    const patterns = [
      /(?:create|add|new)\s+(?:a\s+)?(?:task|todo|item)\s+(?:called|named|for|to|:)?\s*["']?([^"'.!?]+)["']?/i,
      /(?:task|todo|item)\s+(?:called|named|for|to|:)?\s*["']?([^"'.!?]+)["']?/i,
      /(?:create|add|new)\s+(?:a\s+)?(?:task|todo|item)\s+(?:for|to)\s+["']?([^"'.!?]+)["']?/i,
    ];

    for (const pattern of patterns) {
      const match = message.match(pattern);
      if (match && match[1]) {
        return match[1].trim();
      }
    }

    // Fallback: extract text after task keywords
    const taskKeywords = ["task", "todo", "item", "thing to do"];
    for (const keyword of taskKeywords) {
      const index = message.toLowerCase().indexOf(keyword);
      if (index !== -1) {
        const afterKeyword = message.substring(index + keyword.length).trim();
        // Remove common prefixes and suffixes
        return afterKeyword
          .replace(/^(?:called|named|for|to|:|\s)+/i, "")
          .replace(/[.!?]$/, "")
          .trim();
      }
    }

    return message;
  }

  private extractDate(message: string): string {
    // Enhanced date extraction with comprehensive patterns
    const datePatterns = [
      // Relative dates
      /\b(today|tomorrow|yesterday)\b/i,
      /\b(next|this)\s+(week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i,
      /\b(in|after)\s+(\d+)\s+(days|weeks|months|years)\b/i,

      // Specific dates
      /\b(\d{1,2}\/\d{1,2}\/\d{4})\b/,
      /\b(\d{1,2}-\d{1,2}-\d{4})\b/,
      /\b(\d{4}-\d{2}-\d{2})\b/,
      /\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,\s*\d{4})?\b/i,

      // Date ranges
      /\b(from|between)\s+([^,]+?)\s+(?:to|and)\s+([^.!?]+)/i,
    ];

    for (const pattern of datePatterns) {
      const match = message.match(pattern);
      if (match) {
        // For ranges, return the entire range
        if (match[2] && match[3]) {
          return `${match[2]} to ${match[3]}`.trim();
        }
        return match[0].trim();
      }
    }

    return "";
  }

  private extractTime(message: string): string {
    // Enhanced time extraction with better patterns
    const timePatterns = [
      // 12-hour format with AM/PM
      /\b(\d{1,2}:\d{2}\s*(?:am|pm))\b/i,
      /\b(\d{1,2}\s*(?:am|pm))\b/i,

      // 24-hour format
      /\b(\d{1,2}:\d{2})\b/,

      // Time ranges
      /\b(from|at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:to|until|-)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b/i,

      // Relative times
      /\b(morning|afternoon|evening|noon|midnight)\b/i,
      /\b(in|after)\s+(\d+)\s+(minutes|hours)\b/i,
    ];

    for (const pattern of timePatterns) {
      const match = message.match(pattern);
      if (match) {
        // For time ranges, return the entire range
        if (match[2] && match[3]) {
          return `${match[2]} to ${match[3]}`.trim();
        }
        return match[0].trim();
      }
    }

    return "";
  }

  private extractParticipants(message: string): string[] {
    // Enhanced participant extraction
    const patterns = [
      // @mentions
      /@(\w+)/g,

      // Full names (Title Case)
      /\b[A-Z][a-z]+ [A-Z][a-z]+\b/g,

      // "with X", "meeting with X and Y"
      /(?:with|meeting with|call with)\s+([^,.!?]+)/gi,

      // Email addresses
      /\b[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b/g,
    ];

    const participants: string[] = [];

    for (const pattern of patterns) {
      const matches = message.match(pattern);
      if (matches) {
        for (const match of matches) {
          // Clean up the extracted participant
          let participant = match
            .replace(/^(?:with|meeting with|call with)\s+/i, "")
            .replace(/^@/, "")
            .trim();

          if (participant && !participants.includes(participant)) {
            participants.push(participant);
          }
        }
      }
    }

    return participants;
  }

  private extractProject(message: string): string {
    const patterns = [
      /(?:for|in|project)\s+["']?([^"'.!?]+)["']?(?:\s+project)?/i,
      /project\s+["']?([^"'.!?]+)["']?/i,
      /\b(?:#|proj(?:ect)?)\s*(\w+)\b/i,
    ];

    for (const pattern of patterns) {
      const match = message.match(pattern);
      if (match && match[1]) {
        return match[1].trim();
      }
    }

    return "";
  }

  private extractPriority(message: string): string {
    const priorityPatterns = [
      /\b(high|urgent|critical|priority 1|p1)\b/i,
      /\b(medium|normal|standard|priority 2|p2)\b/i,
      /\b(low|minor|low priority|priority 3|p3)\b/i,
    ];

    for (const pattern of priorityPatterns) {
      const match = message.match(pattern);
      if (match) {
        return match[0].toLowerCase();
      }
    }

    return "";
  }

  private extractSearchQuery(message: string): string {
    const patterns = [
      /(?:search|find|look up)\s+(?:for|)\s*["']?([^"'.!?]+)["']?/i,
      /(?:search|find|look up)\s+(?:the|)\s+["']?([^"'.!?]+)["']?/i,
      /(?:where is|show me|get)\s+["']?([^"'.!?]+)["']?/i,
    ];

    for (const pattern of patterns) {
      const match = message.match(pattern);
      if (match && match[1]) {
        return match[1].trim();
      }
    }

    return message; // Fallback to entire message
  }

  private extractDocumentType(message: string): string {
    const docTypes = [
      "report",
      "document",
      "file",
      "spreadsheet",
      "presentation",
      "pdf",
      "word doc",
      "excel",
      "powerpoint",
      "image",
      "photo",
    ];

    for (const docType of docTypes) {
      if (message.toLowerCase().includes(docType)) {
        return docType;
      }
    }

    return "";
  }

  private extractServiceName(message: string): string {
    const services = [
      "google drive",
      "dropbox",
      "slack",
      "github",
      "jira",
      "trello",
      "asana",
      "notion",
      "outlook",
      "gmail",
      "calendar",
    ];

    for (const service of services) {
      if (message.toLowerCase().includes(service)) {
        return service;
      }
    }

    return "";
  }

  private extractWorkflowName(message: string): string {
    const patterns = [
      /(?:run|execute|trigger)\s+(?:the|)\s*["']?([^"'.!?]+)["']?(?:\s+workflow)?/i,
      /workflow\s+["']?([^"'.!?]+)["']?/i,
    ];

    for (const pattern of patterns) {
      const match = message.match(pattern);
      if (match && match[1]) {
        return match[1].trim();
      }
    }

    return "";
  }

  private extractTimePeriod(message: string): string {
    const timePeriodPatterns = [
      // Quarters
      /\b(q[1-4])\s*(\d{4})?\b/i,
      /\b(quarter\s*[1-4])\s*(\d{4})?\b/i,
      /\b(q[1-4]\s*\d{4})\b/i,

      // Years and year ranges
      /\b(\d{4})\b/,
      /\b(\d{4}\s*[-–]\s*\d{4})\b/,
      /\b(\d{4}\s*[-–]\s*\d{2,4})\b/,

      // Relative time periods
      /\b(last|this|next)\s+(year|quarter|month|week)\b/i,
      /\b(previous|current|upcoming)\s+(year|quarter|month)\b/i,

      // Specific months and seasons
      /\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})?\b/i,
      /\b(spring|summer|fall|autumn|winter)\s+(\d{4})?\b/i,

      // Fiscal periods
      /\b(fy\s*\d{4})\b/i,
      /\b(fiscal\s*(year|quarter)\s*\d{4})\b/i,

      // Date ranges
      /\b(from|between)\s+([^,]+?)\s+(?:to|and|through)\s+([^.!?]+)/i,
    ];

    for (const pattern of timePeriodPatterns) {
      const match = message.match(pattern);
      if (match) {
        // For ranges, return the entire range
        if (match[2] && match[3]) {
          return `${match[2]} to ${match[3]}`.trim();
        }
        // For single matches, return the matched text
        return match[0].trim();
      }
    }

    return "";
  }

  private async understandWithLeadAgent(
    message: string,
    context?: ConversationContext,
    options?: { apiKey?: string },
  ): Promise<NLUResponse> {
    // Initialize lead agent if not already done
    if (!this.leadAgent) {
      const apiKey = options?.apiKey || process.env.OPENAI_API_KEY;
      if (!apiKey) {
        throw new Error("OpenAI API key required for lead agent");
      }

      const llmService = new RealLLMService(apiKey, "gpt-4");
      // Create a simple context and functions for the lead agent
      const mockContext = {} as any;
      const mockFunctions = {} as any;
      const mockMemory = {} as any;

      this.leadAgent = new NLULeadAgent(
        llmService,
        mockContext,
        mockMemory,
        mockFunctions,
      );
    }

    try {
      const input = {
        userInput: message,
        userId: context?.userId,
      };

      const enrichedIntent = await this.leadAgent.analyzeIntent(input);

      // Convert enriched intent to NLUResponse format
      return {
        intent: enrichedIntent.primaryGoal || "unknown",
        confidence: enrichedIntent.primaryGoalConfidence || 0.7,
        entities: enrichedIntent.extractedParameters || {},
        action:
          enrichedIntent.suggestedNextAction?.actionType === "invoke_skill"
            ? "execute_skill"
            : "respond",
        parameters: enrichedIntent.extractedParameters || {},
        workflow: enrichedIntent.suggestedNextAction?.skillId,
        requiresConfirmation: false,
        suggestedResponses: [],
        context: context,
      };
    } catch (error) {
      console.error("Lead agent processing failed:", error);
      throw error;
    }
  }

  private getFallbackResponse(message: string): NLUResponse {
    return {
      intent: "unknown",
      confidence: 0.1,
      entities: {},
      action: "respond",
      parameters: { message },
      suggestedResponses: [
        "I'm not sure I understand. Could you rephrase that?",
        "Could you provide more details about what you'd like to do?",
        "I don't recognize that command. Here's what I can help with:",
      ],
    };
  }

  async processConversation(
    messages: Array<{ role: string; content: string }>,
    context: ConversationContext,
  ): Promise<NLUResponse> {
    const lastMessage = messages[messages.length - 1]?.content || "";
    return this.understandMessage(lastMessage, context);
  }

  async getSupportedIntents(): Promise<IntentDefinition[]> {
    return this.intentDefinitions;
  }

  async trainOnExamples(
    examples: Array<{ message: string; intent: string; entities?: any }>,
  ): Promise<{ success: boolean; trainedExamples: number; errors: string[] }> {
    const errors: string[] = [];
    let trainedExamples = 0;

    try {
      console.log(`🧠 Training NLU system on ${examples.length} examples...`);

      for (const example of examples) {
        try {
          // Find the intent definition
          const intentDef = this.intentDefinitions.find(
            (intent) => intent.name === example.intent,
          );

          if (!intentDef) {
            errors.push(`Intent not found: ${example.intent}`);
            continue;
          }

          // Add the example to the intent patterns if not already present
          if (!intentDef.patterns.includes(example.message.toLowerCase())) {
            intentDef.patterns.push(example.message.toLowerCase());
          }

          // Add to examples if not already present
          if (!intentDef.examples.includes(example.message)) {
            intentDef.examples.push(example.message);
          }

          // Store the training example
          this.trainingExamples.push({
            message: example.message,
            intent: example.intent,
            entities: example.entities || {},
            timestamp: new Date(),
          });

          trainedExamples++;
        } catch (error) {
          errors.push(
            `Failed to process example: ${example.message} - ${error}`,
          );
        }
      }

      // Save the updated training examples
      this.saveTrainingExamples();

      console.log(
        `✅ Training completed: ${trainedExamples} examples trained, ${errors.length} errors`,
      );
      return { success: errors.length === 0, trainedExamples, errors };
    } catch (error) {
      console.error("Training failed:", error);
      return { success: false, trainedExamples, errors: [String(error)] };
    }
  }

  async retrainFromExamples(): Promise<{
    success: boolean;
    retrained: number;
  }> {
    console.log("🔄 Retraining NLU from stored examples...");

    let retrained = 0;
    try {
      // Group examples by intent
      const examplesByIntent: Record<
        string,
        Array<{ message: string; entities: any }>
      > = {};

      for (const example of this.trainingExamples) {
        if (!examplesByIntent[example.intent]) {
          examplesByIntent[example.intent] = [];
        }
        examplesByIntent[example.intent].push({
          message: example.message,
          entities: example.entities,
        });
      }

      // Update intent definitions with learned patterns
      for (const intentName in examplesByIntent) {
        const intentDef = this.intentDefinitions.find(
          (intent) => intent.name === intentName,
        );
        if (intentDef) {
          const examples = examplesByIntent[intentName];

          // Add new patterns from examples
          for (const example of examples) {
            const pattern = example.message.toLowerCase();
            if (!intentDef.patterns.includes(pattern)) {
              intentDef.patterns.push(pattern);
            }

            if (!intentDef.examples.includes(example.message)) {
              intentDef.examples.push(example.message);
            }
          }

          retrained += examples.length;
        }
      }

      console.log(`✅ Retraining completed: ${retrained} examples processed`);
      return { success: true, retrained };
    } catch (error) {
      console.error("Retraining failed:", error);
      return { success: false, retrained: 0 };
    }
  }

  getTrainingStats() {
    const statsByIntent: Record<string, number> = {};

    for (const example of this.trainingExamples) {
      statsByIntent[example.intent] = (statsByIntent[example.intent] || 0) + 1;
    }

    return {
      totalExamples: this.trainingExamples.length,
      examplesByIntent: statsByIntent,
      oldestExample:
        this.trainingExamples.length > 0
          ? this.trainingExamples.reduce((oldest, current) =>
              current.timestamp < oldest.timestamp ? current : oldest,
            ).timestamp
          : null,
      newestExample:
        this.trainingExamples.length > 0
          ? this.trainingExamples.reduce((newest, current) =>
              current.timestamp > newest.timestamp ? current : newest,
            ).timestamp
          : null,
    };
  }

  clearTrainingData() {
    const count = this.trainingExamples.length;
    this.trainingExamples = [];

    try {
      const trainingPath = path.join(
        path.dirname(this.configPath),
        "training-examples.json",
      );
      if (fs.existsSync(trainingPath)) {
        fs.unlinkSync(trainingPath);
      }
    } catch (error) {
      console.warn("Failed to delete training file:", error);
    }

    console.log(`🧹 Cleared ${count} training examples`);
    return { cleared: count };
  }

  // Performance monitoring methods
  getMetrics() {
    return {
      ...this.metrics,
      successRate:
        this.metrics.totalRequests > 0
          ? (this.metrics.successfulRequests / this.metrics.totalRequests) * 100
          : 0,
      mostUsedIntent:
        Object.entries(this.metrics.intentDistribution).sort(
          ([, a], [, b]) => b - a,
        )[0]?.[0] || "none",
      mostUsedService:
        Object.entries(this.metrics.serviceUsage).sort(
          ([, a], [, b]) => b - a,
        )[0]?.[0] || "none",
    };
  }

  resetMetrics() {
    this.metrics = {
      totalRequests: 0,
      successfulRequests: 0,
      failedRequests: 0,
      averageProcessingTime: 0,
      intentDistribution: {},
      serviceUsage: {},
      lastRequestTime: null,
    };
  }

  async getPerformanceReport(): Promise<{
    summary: any;
    topIntents: Array<{ intent: string; count: number }>;
    serviceBreakdown: Array<{
      service: string;
      count: number;
      percentage: number;
    }>;
  }> {
    const metrics = this.getMetrics();
    const total = metrics.totalRequests || 1;

    return {
      summary: {
        totalRequests: metrics.totalRequests,
        successRate: Math.round(metrics.successRate * 100) / 100,
        averageProcessingTime: Math.round(metrics.averageProcessingTime),
        lastRequestTime: metrics.lastRequestTime,
      },
      topIntents: Object.entries(metrics.intentDistribution)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
        .map(([intent, count]) => ({ intent, count })),
      serviceBreakdown: Object.entries(metrics.serviceUsage)
        .map(([service, count]) => ({
          service,
          count,
          percentage: Math.round((count / total) * 1000) / 10,
        }))
        .sort((a, b) => b.count - a.count),
    };
  }
}

// Singleton instance
export const nluService = new NLUService();

// Configuration management methods
export async function reloadIntentDefinitions(
  configPath?: string,
): Promise<void> {
  const newService = new NLUService(configPath);
  // Update the singleton instance's intent definitions
  (nluService as any).intentDefinitions =
    await newService.getSupportedIntents();
}

// Training system exports
export async function trainNLU(
  examples: Array<{ message: string; intent: string; entities?: any }>,
) {
  return nluService.trainOnExamples(examples);
}

export async function retrainNLU() {
  return nluService.retrainFromExamples();
}

export function getNLUTrainingStats() {
  return nluService.getTrainingStats();
}

export function clearNLUTrainingData() {
  return nluService.clearTrainingData();
}

// Performance monitoring exports
export function getNLUMetrics() {
  return nluService.getMetrics();
}

export function resetNLUMetrics() {
  return nluService.resetMetrics();
}

export async function getNLUPerformanceReport() {
  return nluService.getPerformanceReport();
}

export async function exportIntentDefinitions(): Promise<IntentDefinition[]> {
  return nluService.getSupportedIntents();
}

export async function importIntentDefinitions(
  intents: IntentDefinition[],
): Promise<void> {
  // This would typically save to the config file
  console.log(`Imported ${intents.length} intent definitions`);
  // For now, just update the in-memory definitions
  (nluService as any).intentDefinitions = intents;
}

// Default export for backward compatibility
export async function understandMessage(
  message: string,
  context?: ConversationContext,
  options?: { service?: "openai" | "rules" | "hybrid"; apiKey?: string },
): Promise<NLUResponse> {
  return nluService.understandMessage(message, context, options);
}

// Types are already exported at the top of the file
