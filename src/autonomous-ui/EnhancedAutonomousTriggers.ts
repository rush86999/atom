import { EventEmitter } from 'events';
import { AutonomousWorkflowService } from '../services/autonomousWorkflowService';
import { VisualScreenAnalyzer } from './visualScreenAnalyzer';
import { AutonomousTestRunner } from './autonomousTestRunner';

interface TriggerEvent {
  id: string;
  type: 'time' | 'webhook' | 'condition' | 'manual' | 'external-api';
  workflowId: string;
  context: Record<string, any>;
  schedule?: string;
  conditions?: TriggerCondition[];
  actions?: any[];
  metadata: {
    createdAt: string;
    lastRunAt?: string;
    successCount: number;
    failureCount: number;
    averageDelay: number;
  };
}

interface TriggerCondition {
  type: 'element-state' | 'page-content' | 'api-response' | 'data-value' | 'performance-metric';
  selector?: string;
  expectedValue?: any;
  operator: 'equals' | 'contains' | 'greater-than' | 'less-than' | 'exists';
  timeout?: number;
}

interface SmartTrigger {
  id: string;
  name: string;
  workflowId: string;
  triggerType: 'web-scraping' | 'sales-monitor' | 'performance-check' | 'content-change' | 'api-monitor';
  source: 'web' | 'app' | 'api' | 'database' | 'file';
  parameters: Record<string, any>;
  conditions: TriggerCondition[];
  schedule?: string;
  enablePredictive: boolean;
  learningEnabled: boolean;
  notificationConfig: {
    success: boolean;
    failure: boolean;
    retryAttempts: number;
    webhookUrl?: string;
  };
}

interface WorkflowInsights {
  successRate: number;
  averageExecutionTime: number;
  improvementSuggestions: string[];
  predictiveOpportunities: string[];
}

export class EnhancedAutonomousTriggers extends EventEmitter {
  private workflowService: AutonomousWorkflowService;
  private visualAnalyzer: VisualScreenAnalyzer | null = null;
  private triggers: Map<string, SmartTrigger> = new Map();
  private triggerEvents: Map<string, TriggerEvent[]> = new Map();
  private insightsEngine: Map<string, WorkflowInsights> = new Map();
  private isRunning = false;
  private monitoringInterval: NodeJS.Timeout | null = null;

  constructor(workflowService: AutonomousWorkflowService) {
    super();
    this.workflowService = workflowService;
  }

  async initialize(): Promise<void> {
    await this.workflowService.initialize();

    if (this.visualAnalyzer) {
      await this.visualAnalyzer.init();
    }

    this.startProactiveMonitoring();
  }

  // Smart trigger creation methods
  createWebMonitoringTrigger(workflowId: string, url: string, selector: string, expectedChange: string): SmartTrigger {
    const trigger: SmartTrigger = {
      id: `web-monitor-${Date.now()}`,
      name: `Monitor ${selector} on ${url}`,
      workflowId,
      triggerType: 'content-change',
      source: 'web',
      parameters: { url, selector, expectedChange },
      conditions: [{
        type: 'page-content',
        selector,
        operator: 'contains',
        expectedValue: expectedChange
      }],
      schedule: '*/15 * * * *', // Every 15 minutes
      enablePredictive: true,
      learningEnabled: true,
      notificationConfig: {
        success: true,
        failure: true,
        retryAttempts: 3
      }
    };

    this.triggers.set(trigger.id, trigger);
    return trigger;
  }

  createSalesTrigger(workflowId: string, shopifyStore: string, minRevenue: number): SmartTrigger {
    return {
      id: `sales-monitor-${Date.now()}`,
      name: `Sales threshold monitor for ${shopifyStore}`,
      workflowId,
      triggerType: 'sales-monitor',
      source: 'api',
      parameters: { shopifyStore, minRevenue },
      conditions: [{
        type: 'data-value',
        operator: 'greater-than',
        expectedValue: minRevenue
      }],
      schedule: '0 */4 * * *', // Every 4 hours
      enablePredictive: true,
      learningEnabled: true,
      notificationConfig: {
        success: true,
        failure: false,
        retryAttempts: 2
      }
    };
  }

  createPerformanceTrigger(workflowId: string, url: string, maxLoadTime: number): SmartTrigger {
    return {
      id: `performance-${Date.now()}`,
      name: `Performance check for ${url}`,
      workflowId,
      triggerType: 'performance-check',
      source: 'web',
      parameters: { url, maxLoadTime },
      conditions: [{
        type: 'performance-metric',
        operator: 'less-than',
        expectedValue: maxLoadTime
      }],
      schedule
