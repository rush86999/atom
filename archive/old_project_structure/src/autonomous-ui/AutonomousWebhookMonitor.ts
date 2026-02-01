import { EventEmitter } from 'events';
import * as crypto from 'crypto';
import axios from 'axios';
import { AutonomousWorkflowService } from '../services/autonomousWorkflowService';
import { VisualScreenAnalyzer } from './visualScreenAnalyzer';

interface WebhookConfig {
  id: string;
  name: string;
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  headers: Record<string, string>;
  body?: any;
  expectedStatus: number[];
  retryConfig: {
    attempts: number;
    delay: number;
    backoff: 'linear' | 'exponential';
  };
  timeout: number;
  filter?: {
    jsonPath?: string;
    expectedValue?: any;
    operator: 'equals' | 'contains' | 'greater' | 'less';
  };
}

interface IncomingWebhook {
  id: string;
  configId: string;
  signature: string;
  payload: any;
  headers: Record<string, string>;
  timestamp: number;
  processed: boolean;
}

interface SmartMonitoringResult {
  webhookId: string;
  success: boolean;
  responseTime: number;
  dataMatched: boolean;
  retryCount: number;
  error?: string;
  extractedData?: any;
}

interface PredictiveAlert {
  webhookId: string;
  alertType: 'degradation' | 'failure_rate' | 'data_anomaly' | 'timeout';
  confidence: number;
  recommendation: string;
  timestamp: number;
}

export class AutonomousWebhookMonitor extends EventEmitter {
  private configs: Map<string, WebhookConfig> = new Map();
  private incoming: Map<string, IncomingWebhook[]> = new Map();
  private monitoring: Map<string, NodeJS.Timeout> = new Map();
  private workflowService: AutonomousWorkflowService;
  private analyzer: VisualScreenAnalyzer;
  private cache: Map<string, any> = new Map();
  private isRunning = false;

  constructor(workflowService: AutonomousWorkflowService) {
    super();
    this.workflowService = workflowService;
    this.analyzer = new VisualScreenAnalyzer();
  }

  async initialize() {
    await this.analyzer.init();
    this.isRunning = true;
    this.startAutoMonitoring();
  }

  async shutdown() {
    this.isRunning = false;
    this.monitoring.forEach(timeout => clearInterval(timeout));
    this.monitoring.clear();
    await this.analyzer.shutdown();
  }

  // Create smart webhook trigger
  createSmartWebhookTrigger(config: Partial<WebhookConfig>): WebhookConfig {
    const id = `webhook-${Date.now()}`;
    const webhookConfig: WebhookConfig = {
      id,
      name: config.name || `Webhook ${id}`,
      url: config.url || '',
      method: config.method || 'POST',
      headers: config.headers || {},
      expectedStatus: config.expectedStatus || [200, 201, 202],
      retryConfig: {
        attempts: 3,
        delay: 1000,
        backoff: 'exponential',
        ...config.retryConfig
      },
      timeout: config.timeout || 30000,
      filter: config.filter
    };

    this.configs.set(id, webhookConfig);
    this.startMonitoringWebhook(webhookConfig);
    return webhookConfig;
  }

  // Process incoming webhook
  async processIncomingWebhook(
    configId: string,
    payload: any,
    headers: Record<string, string> = {},
    signature?: string
  ): Promise<void> {
    const config = this.configs.get(configId);
    if (!config) throw new Error(`Webhook config ${configId} not found`);

    const webhook: IncomingWebhook = {
      id: crypto.randomUUID(),
      configId,
      signature: signature || this.generateSignature(payload, config),
      payload,
      headers,
      timestamp: Date.now(),
      processed: false
    };

    if (!this.incoming.has(configId)) {
      this.incoming.set(configId, []);
    }

    this.incoming.get(configId)!.push(webhook);

    // Process immediately with intelligence
    await this.intelligentlyProcessWebhook(webhook, config);
  }

  // Intelligent webhook processing
  private async intelligentlyProcessWebhook(webhook: IncomingWebhook, config: WebhookConfig): Promise<void> {
    try {
      // Extract insights from payload using AI
      const insights = await this.extractWebhookInsights(webhook.payload, config);

      // Filter based on conditions
      const shouldTrigger = await this.evaluateWebhookConditions(webhook, config);

      if (shouldTrigger) {
        // Trigger associated workflow with enriched context
        await this.triggerAssociatedWorkflow(webhook, insights);
      }

      webhook.processed = true;

    } catch (error) {
      console.error('Error processing webhook:', error);
      this.emit('webhook-error', { webhook, error });
    }
  }
