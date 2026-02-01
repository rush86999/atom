/**
 * Shared NLU Service Interface
 * Common interface for both desktop and web implementations
 */

export interface Intent {
  name: string;
  confidence: number;
  entities: Record<string, any>;
}

export interface Entity {
  entity: string;
  value: string;
  confidence: number;
}

export interface SkillExecutionContext {
  intent: Intent;
  entities: Entity[];
  userInput: string;
  sessionId?: string;
  userId?: string;
}

export interface NLUResponse {
  intent: Intent | null;
  entities: Entity[];
  confidence: number;
  action?: string;
  parameters?: Record<string, any>;
}

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
  platforms: string[];
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
  platformContext?: Record<string, any>;
  crossPlatformHistory?: Array<{
    platform: string;
    action: string;
    timestamp: Date;
    result: any;
  }>;
  userPreferences?: {
    automationLevel: 'minimal' | 'moderate' | 'full';
    communicationStyle: 'professional' | 'friendly' | 'interactive';
    preferredServices: string[];
  };
}

export interface INLUService {
  // Core NLU functionality
  processInput(userInput: string, context?: ConversationContext): Promise<NLUResponse>;

  // Intent management
  getSupportedIntents(): Promise<string[]>;
  validateIntent(intentName: string, userInput: string): Promise<boolean>;

  // Cross-platform capabilities
  processCrossPlatformInput(userInput: string, context?: ConversationContext): Promise<CrossPlatformIntent>;
  getCrossPlatformActions(): Promise<string[]>;

  // Context management
  updateContext(sessionId: string, context: Partial<ConversationContext>): Promise<void>;
  getContext(sessionId: string): Promise<ConversationContext | null>;

  // Data integration
  createDataIntegrationPlan(sourceData: any, targetPlatforms: string[]): Promise<DataIntegrationPlan>;
  executeDataIntegration(plan: DataIntegrationPlan, context: ConversationContext): Promise<any>;
}

// Export type aliases for compatibility
export type nlpService = INLUService;
export type nluService = INLUService;
