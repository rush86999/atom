import { EventEmitter } from "events";
import { Logger } from "../utils/logger";
import { MultiIntegrationWorkflowEngine, OrchestrationConfig } from "./MultiIntegrationWorkflowEngine";
import { EnhancedWorkflowService } from "./EnhancedWorkflowService";
import { IntegrationRegistry, IntegrationConfiguration } from "./IntegrationRegistry";
import { WorkflowExecution, WorkflowDefinition } from "./MultiIntegrationWorkflowEngine";

/**
 * Comprehensive Orchestration Manager
 * 
 * This is the main entry point for the multi-integration workflow orchestration system.
 * It coordinates between the workflow engine, enhanced workflow service, and integration registry.
 */

export interface OrchestrationManagerConfig extends OrchestrationConfig {
  enableAutoOptimization: boolean;
  enableCircuitBreaker: boolean;
  enableDistributedTracing: boolean;
  enableMetricsCollection: boolean;
  enablePerformanceMonitoring: boolean;
  optimizationInterval: number; // milliseconds
  metricsRetentionPeriod: number; // milliseconds
  maxWorkflowExecutionHistory: number;
  enableAIOptimizations: boolean;
  enablePredictiveScaling: boolean;
}

export interface OrchestrationMetrics {
  timestamp: Date;
  system: {
    totalWorkflows: number;
    activeExecutions: number;
    queuedExecutions: number;
    totalIntegrations: number;
    healthyIntegrations: number;
    connectedIntegrations: number;
  };
  performance: {
    averageExecutionTime: number;
    successRate: number;
    throughput: number; // executions per minute
    errorRate: number;
    resourceUtilization: number; // percentage
  };
  costs: {
    totalCost: number;
    costBreakdown: Record<string, number>;
    costTrend: number; // percentage change
  };
  predictions: {
    expectedLoad: number; // next hour
    recommendedScaling: {
      addExecutors: boolean;
      removeExecutors: boolean;
      targetConcurrency: number;
    };
    potentialBottlenecks: string[];
  };
}

export interface OrchestrationAlert {
  id: string;
  type: 'error' | 'warning' | 'info' | 'critical';
  category: 'system' | 'workflow' | 'integration' | 'performance' | 'security';
  title: string;
  message: string;
  details: Record<string, any>;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: Date;
  resolved: boolean;
  resolvedAt?: Date;
  resolvedBy?: string;
  actions: Array<{
    type: 'acknowledge' | 'resolve' | 'escalate' | 'auto_fix';
    label: string;
    description: string;
  }>;
}

export interface OrchestrationSnapshot {
  timestamp: Date;
  workflows: {
    total: number;
    active: number;
    completed: number;
    failed: number;
    averageDuration: number;
  };
  integrations: {
    total: number;
    healthy: number;
    unhealthy: number;
    averageResponseTime: number;
    totalRequests: number;
    errorRate: number;
  };
  system: {
    uptime: number;
    memoryUsage: number;
    cpuUsage: number;
    diskUsage: number;
    networkLatency: number;
  };
  alerts: {
    active: number;
    critical: number;
    warnings: number;
    resolved: number;
  };
}

export interface WorkflowOptimizationResult {
  workflowId: string;
  optimizations: Array<{
    type: 'parallel' | 'caching' | 'batching' | 'retry' | 'timeout' | 'resource';
    description: string;
    impact: 'low' | 'medium' | 'high';
    estimatedImprovement: number; // percentage
    implementationComplexity: 'simple' | 'moderate' | 'complex';
    changes: Record<string, any>;
  }>;
  overallScore: number; // 0-100
  recommendations: string[];
  autoApplicable: boolean;
  riskAssessment: 'low' | 'medium' | 'high';
}

export interface ScalingDecision {
  timestamp: Date;
  currentLoad: number;
  predictedLoad: number;
  decision: 'scale_up' | 'scale_down' | 'maintain';
  newConcurrency: number;
  reason: string;
  confidence: number; // 0-1
  estimatedCostImpact: number;
  estimatedPerformanceImpact: number;
}

export class OrchestrationManager extends EventEmitter {
  private logger: Logger;
  private config: OrchestrationManagerConfig;
  private workflowEngine: MultiIntegrationWorkflowEngine;
  private workflowService: EnhancedWorkflowService;
  private integrationRegistry: IntegrationRegistry;
  
  private metrics: OrchestrationMetrics[];
  private alerts: OrchestrationAlert[];
  private snapshots: OrchestrationSnapshot[];
  private optimizations: Map<string, WorkflowOptimizationResult>;
  private scalingHistory: ScalingDecision[];
  
  private startTime: Date;
  private metricsTimer?: NodeJS.Timeout;
  private optimizationTimer?: NodeJS.Timeout;
  private healthCheckTimer?: NodeJS.Timeout;
  private cleanupTimer?: NodeJS.Timeout;

  constructor(config: OrchestrationManagerConfig) {
    super();
    this.logger = new Logger("OrchestrationManager");
    this.config = {
      enableAutoOptimization: true,
      enableCircuitBreaker: true,
      enableDistributedTracing: true,
      enableMetricsCollection: true,
      enablePerformanceMonitoring: true,
      optimizationInterval: 300000, // 5 minutes
      metricsRetentionPeriod: 7 * 24 * 60 * 60 * 1000, // 7 days
      maxWorkflowExecutionHistory: 10000,
      enableAIOptimizations: true,
      enablePredictiveScaling: true,
      ...config,
    };

    this.startTime = new Date();
    this.metrics = [];
    this.alerts = [];
    this.snapshots = [];
    this.optimizations = new Map();
    this.scalingHistory = [];

    this.initializeComponents();
    this.setupEventListeners();
    this.startBackgroundTasks();

    this.logger.info("Orchestration Manager initialized");
  }

  private initializeComponents(): void {
    // Initialize workflow engine
    this.workflowEngine = new MultiIntegrationWorkflowEngine({
      maxConcurrentExecutions: this.config.maxConcurrentExecutions,
      maxStepsPerExecution: this.config.maxStepsPerExecution,
      defaultTimeout: this.config.defaultTimeout,
      defaultRetryAttempts: this.config.defaultRetryAttempts,
      enableCaching: this.config.enableCaching,
      enableMetrics: this.config.enableMetrics,
      enableOptimization: this.config.enableOptimization,
      healthCheckInterval: this.config.healthCheckInterval,
      integrationHealthThreshold: this.config.integrationHealthThreshold,
      autoRetryFailures: this.config.autoRetryFailures,
      logLevel: this.config.logLevel,
    });

    // Initialize enhanced workflow service
    this.workflowService = new EnhancedWorkflowService(this.workflowEngine);

    // Initialize integration registry
    this.integrationRegistry = new IntegrationRegistry();

    this.logger.info("All orchestration components initialized");
  }

  private setupEventListeners(): void {
    // Workflow engine events
    this.workflowEngine.on('workflow-execution-started', (data) => {
      this.handleWorkflowExecutionStarted(data);
    });

    this.workflowEngine.on('workflow-execution-completed', (data) => {
      this.handleWorkflowExecutionCompleted(data);
    });

    this.workflowEngine.on('workflow-execution-failed', (data) => {
      this.handleWorkflowExecutionFailed(data);
    });

    this.workflowEngine.on('integration-health-changed', (data) => {
      this.handleIntegrationHealthChanged(data);
    });

    // Workflow service events
    this.workflowService.on('workflow-completed', (data) => {
      this.handleWorkflowServiceCompleted(data);
    });

    this.workflowService.on('workflow-failed', (data) => {
      this.handleWorkflowServiceFailed(data);
    });

    // Integration registry events
    this.integrationRegistry.on('integration-event', (data) => {
      this.handleIntegrationEvent(data);
    });

    this.integrationRegistry.on('connection-health-changed', (data) => {
      this.handleConnectionHealthChanged(data);
    });

    this.logger.info("Event listeners configured");
  }

  private startBackgroundTasks(): void {
    // Metrics collection
    if (this.config.enableMetricsCollection) {
      this.metricsTimer = setInterval(() => {
        this.collectMetrics();
      }, 60000); // Every minute
    }

    // Auto-optimization
    if (this.config.enableAutoOptimization) {
      this.optimizationTimer = setInterval(() => {
        this.performAutoOptimization();
      }, this.config.optimizationInterval);
    }

    // Health checks
    this.healthCheckTimer = setInterval(() => {
      this.performSystemHealthCheck();
    }, 30000); // Every 30 seconds

    // Cleanup old data
    this.cleanupTimer = setInterval(() => {
      this.performCleanup();
    }, 3600000); // Every hour

    this.logger.info("Background tasks started");
  }

  // Public API - Workflow Management
  async createWorkflow(workflow: WorkflowDefinition): Promise<string> {
    try {
      await this.workflowEngine.registerWorkflow(workflow);
      
      this.logger.info(`Workflow created: ${workflow.name} (${workflow.id})`);
      this.emit("workflow-created", { workflowId: workflow.id, name: workflow.name });
      
      return workflow.id;
    } catch (error) {
      this.logger.error(`Failed to create workflow: ${error.message}`, error);
      throw error;
    }
  }

  async executeWorkflow(
    workflowId: string,
    triggeredBy: string,
    parameters: Record<string, any> = {}
  ): Promise<string> {
    try {
      const executionId = await this.workflowEngine.executeWorkflow(workflowId, triggeredBy, parameters);
      
      this.logger.info(`Workflow execution started: ${workflowId} -> ${executionId}`);
      this.emit("workflow-execution-triggered", { workflowId, executionId, triggeredBy });
      
      return executionId;
    } catch (error) {
      this.logger.error(`Failed to execute workflow ${workflowId}: ${error.message}`, error);
      throw error;
    }
  }

  async getWorkflowExecution(executionId: string): Promise<WorkflowExecution | null> {
    return await this.workflowEngine.getExecution(executionId);
  }

  async getWorkflowAnalytics(workflowId: string): Promise<any> {
    return await this.workflowEngine.getWorkflowAnalytics(workflowId);
  }

  async optimizeWorkflow(workflowId: string, autoApply: boolean = false): Promise<WorkflowOptimizationResult> {
    try {
      const optimization = await this.workflowService.optimizeWorkflow(workflowId);
      
      const result: WorkflowOptimizationResult = {
        workflowId,
        optimizations: optimization.optimizations,
        overallScore: optimization.overallScore,
        recommendations: optimization.recommendations,
        autoApplicable: optimization.optimizations.every(opt => 
          opt.impact === 'low' || opt.impact === 'medium'
        ),
        riskAssessment: this.assessOptimizationRisk(optimization.optimizations),
      };

      this.optimizations.set(workflowId, result);

      if (autoApply && result.autoApplicable) {
        await this.applyOptimization(workflowId, result);
      }

      this.emit("workflow-optimized", { workflowId, result });
      return result;
    } catch (error) {
      this.logger.error(`Failed to optimize workflow ${workflowId}: ${error.message}`, error);
      throw error;
    }
  }

  // Public API - Integration Management
  async configureIntegration(
    integrationId: string,
    userId: string,
    settings: Record<string, any>,
    credentials: IntegrationConfiguration['credentials']
  ): Promise<string> {
    try {
      const configKey = await this.integrationRegistry.createConfiguration(
        integrationId,
        userId,
        settings,
        credentials
      );

      this.logger.info(`Integration configured: ${integrationId} for user ${userId}`);
      this.emit("integration-configured", { integrationId, userId, configKey });

      return configKey;
    } catch (error) {
      this.logger.error(`Failed to configure integration ${integrationId}: ${error.message}`, error);
      throw error;
    }
  }

  async activateIntegration(integrationId: string, userId: string): Promise<boolean> {
    try {
      const success = await this.integrationRegistry.activateConfiguration(integrationId, userId);
      
      if (success) {
        // Get integration capability and register with workflow engine
        const integration = await this.integrationRegistry.getIntegration(integrationId);
        if (integration) {
          const capability = this.convertToCapability(integration);
          await this.workflowEngine.registerIntegration(capability);
        }

        this.emit("integration-activated", { integrationId, userId });
      }

      return success;
    } catch (error) {
      this.logger.error(`Failed to activate integration ${integrationId}: ${error.message}`, error);
      throw error;
    }
  }

  async getIntegrationHealth(integrationId?: string): Promise<any> {
    if (integrationId) {
      return await this.integrationRegistry.getIntegrationHealth(integrationId);
    }
    
    // Return overall system health
    const integrations = await this.integrationRegistry.listIntegrations();
    const healthChecks = await Promise.all(
      integrations.map(async (integration) => {
        const health = await this.integrationRegistry.getIntegrationHealth(integration.id);
        return { integrationId: integration.id, health };
      })
    );

    return {
      totalIntegrations: integrations.length,
      healthyIntegrations: healthChecks.filter(hc => hc.health?.overallScore >= 80).length,
      integrations: healthChecks
    };
  }

  // Public API - Monitoring and Analytics
  async getMetrics(timeRange?: { start: Date; end: Date }): Promise<OrchestrationMetrics[]> {
    if (timeRange) {
      return this.metrics.filter(metric => 
        metric.timestamp >= timeRange.start && metric.timestamp <= timeRange.end
      );
    }
    return [...this.metrics];
  }

  async getCurrentMetrics(): Promise<OrchestrationMetrics> {
    return await this.collectCurrentMetrics();
  }

  async getAlerts(category?: string, severity?: string): Promise<OrchestrationAlert[]> {
    let alerts = [...this.alerts].filter(alert => !alert.resolved);

    if (category) {
      alerts = alerts.filter(alert => alert.category === category);
    }
    if (severity) {
      alerts = alerts.filter(alert => alert.severity === severity);
    }

    return alerts.sort((a, b) => {
      const severityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
      return severityOrder[b.severity] - severityOrder[a.severity];
    });
  }

  async createAlert(
    type: OrchestrationAlert['type'],
    category: OrchestrationAlert['category'],
    title: string,
    message: string,
    details: Record<string, any> = {},
    severity: OrchestrationAlert['severity'] = 'medium'
  ): Promise<string> {
    const alertId = `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const alert: OrchestrationAlert = {
      id: alertId,
      type,
      category,
      title,
      message,
      details,
      severity,
      timestamp: new Date(),
      resolved: false,
      actions: this.generateAlertActions(type, category, severity),
    };

    this.alerts.push(alert);
    this.emit("alert-created", { alert });

    this.logger.warn(`Alert created: ${title} (${alertId})`);
    return alertId;
  }

  async resolveAlert(alertId: string, resolvedBy: string): Promise<boolean> {
    const alert = this.alerts.find(a => a.id === alertId);
    if (!alert || alert.resolved) {
      return false;
    }

    alert.resolved = true;
    alert.resolvedAt = new Date();
    alert.resolvedBy = resolvedBy;

    this.emit("alert-resolved", { alertId, resolvedBy });
    this.logger.info(`Alert resolved: ${alert.title} (${alertId})`);

    return true;
  }

  async getSystemSnapshot(): Promise<OrchestrationSnapshot> {
    return await this.captureSystemSnapshot();
  }

  async getScalingHistory(limit: number = 10): Promise<ScalingDecision[]> {
    return this.scalingHistory.slice(-limit);
  }

  // Background Task Methods
  private async collectMetrics(): Promise<void> {
    try {
      const metrics = await this.collectCurrentMetrics();
      this.metrics.push(metrics);

      // Enforce retention period
      const cutoff = new Date(Date.now() - this.config.metricsRetentionPeriod);
      this.metrics = this.metrics.filter(metric => metric.timestamp > cutoff);

      this.emit("metrics-collected", { metrics });
    } catch (error) {
      this.logger.error(`Failed to collect metrics: ${error.message}`, error);
    }
  }

  private async collectCurrentMetrics(): Promise<OrchestrationMetrics> {
    const systemHealth = this.workflowEngine.getSystemHealth();
    const integrationHealth = await this.getIntegrationHealth();
    const activeExecutions = this.workflowEngine.getActiveExecutions();
    
    // Calculate performance metrics
    const recentMetrics = this.metrics.slice(-60); // Last hour
    const averageExecutionTime = recentMetrics.length > 0 
      ? recentMetrics.reduce((sum, m) => sum + m.performance.averageExecutionTime, 0) / recentMetrics.length 
      : 0;
    
    const successRate = recentMetrics.length > 0
      ? recentMetrics.reduce((sum, m) => sum + m.performance.successRate, 0) / recentMetrics.length
      : 1.0;

    const throughput = activeExecutions.length > 0 ? activeExecutions.length : 0;
    const errorRate = 1 - successRate;
    const resourceUtilization = systemHealth.activeExecutions / this.config.maxConcurrentExecutions;

    // Predictive metrics (simplified)
    const expectedLoad = this.predictLoad();
    const recommendedScaling = this.calculateRecommendedScaling(expectedLoad, resourceUtilization);
    const potentialBottlenecks = this.identifyPotentialBottlenecks();

    return {
      timestamp: new Date(),
      system: {
        totalWorkflows: systemHealth.totalWorkflows,
        activeExecutions: systemHealth.activeExecutions,
        queuedExecutions: systemHealth.queuedExecutions,
        totalIntegrations: systemHealth.totalIntegrations,
        healthyIntegrations: integrationHealth.healthyIntegrations,
        connectedIntegrations: integrationHealth.totalIntegrations,
      },
      performance: {
        averageExecutionTime,
        successRate,
        throughput,
        errorRate,
        resourceUtilization,
      },
      costs: {
        totalCost: 0, // Would calculate actual costs
        costBreakdown: {},
        costTrend: 0,
      },
      predictions: {
        expectedLoad,
        recommendedScaling,
        potentialBottlenecks,
      },
    };
  }

  private async performAutoOptimization(): Promise<void> {
    if (!this.config.enableAutoOptimization) {
      return;
    }

    try {
      const workflows = this.workflowEngine.getRegisteredWorkflows();
      
      for (const workflow of workflows) {
        const analytics = await this.workflowEngine.getWorkflowAnalytics(workflow.id);
        
        if (analytics && analytics.successRate < 0.8 || analytics.averageExecutionTime > 60000) {
          await this.optimizeWorkflow(workflow.id, false);
        }
      }

      this.emit("auto-optimization-completed");
    } catch (error) {
      this.logger.error(`Auto-optimization failed: ${error.message}`, error);
    }
  }

  private async performSystemHealthCheck(): Promise<void> {
    try {
      const snapshot = await this.captureSystemSnapshot();
      this.snapshots.push(snapshot);

      // Keep only last 1000 snapshots
      if (this.snapshots.length > 1000) {
        this.snapshots = this.snapshots.slice(-1000);
      }

      // Check for issues that need alerts
      await this.checkSystemHealth(snapshot);

      this.emit("health-check-completed", { snapshot });
    } catch (error) {
      this.logger.error(`System health check failed: ${error.message}`, error);
    }
  }

  private async performCleanup(): Promise<void> {
    try {
      // Clean up old metrics
      const metricsCutoff = new Date(Date.now() - this.config.metricsRetentionPeriod);
      this.metrics = this.metrics.filter(metric => metric.timestamp > metricsCutoff);

      // Clean up old alerts (keep resolved alerts for 30 days)
      const alertsCutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      this.alerts = this.alerts.filter(alert => 
        !alert.resolved || (alert.resolvedAt && alert.resolvedAt > alertsCutoff)
      );

      // Clean up old snapshots (keep last 1000)
      if (this.snapshots.length > 1000) {
        this.snapshots = this.snapshots.slice(-1000);
      }

      this.logger.info("Cleanup completed");
    } catch (error) {
      this.logger.error(`Cleanup failed: ${error.message}`, error);
    }
  }

  // Event Handlers
  private handleWorkflowExecutionStarted(data: any): void {
    this.logger.info(`Workflow execution started: ${data.workflowId} -> ${data.executionId}`);
    this.emit("workflow-started", data);
  }

  private handleWorkflowExecutionCompleted(data: any): void {
    this.logger.info(`Workflow execution completed: ${data.executionId}`);
    this.emit("workflow-completed", data);
  }

  private handleWorkflowExecutionFailed(data: any): void {
    this.logger.error(`Workflow execution failed: ${data.executionId}`, data.error);
    
    // Create alert for critical workflow failures
    if (data.workflowId.includes('critical') || data.workflowId.includes('production')) {
      this.createAlert(
        'error',
        'workflow',
        `Critical Workflow Failed: ${data.workflowId}`,
        `Workflow execution ${data.executionId} failed with error: ${data.error?.message || 'Unknown error'}`,
        { workflowId: data.workflowId, executionId: data.executionId, error: data.error },
        'high'
      );
    }
    
    this.emit("workflow-failed", data);
  }

  private handleIntegrationHealthChanged(data: any): void {
    if (!data.isHealthy && data.wasHealthy) {
      this.createAlert(
        'warning',
        'integration',
        `Integration Unhealthy: ${data.integrationId}`,
        `Integration ${data.integrationId} has become unhealthy`,
        { integrationId: data.integrationId },
        'medium'
      );
    }

    this.emit("integration-health-changed", data);
  }

  private handleWorkflowServiceCompleted(data: any): void {
    this.emit("workflow-service-completed", data);
  }

  private handleWorkflowServiceFailed(data: any): void {
    this.logger.error(`Workflow service failed: ${data.error}`, data);
    this.emit("workflow-service-failed", data);
  }

  private handleIntegrationEvent(data: any): void {
    this.emit("integration-event", data);
  }

  private handleConnectionHealthChanged(data: any): void {
    if (!data.isHealthy && data.wasHealthy) {
      this.createAlert(
        'warning',
        'integration',
        `Connection Unhealthy: ${data.connectionId}`,
        `Connection ${data.connectionId} has become unhealthy`,
        { connectionId: data.connectionId },
        'medium'
      );
    }

    this.emit("connection-health-changed", data);
  }

  // Utility Methods
  private convertToCapability(integration: any): IntegrationCapability {
    return {
      id: integration.id,
      name: integration.displayName,
      integrationType: integration.category,
      supportedActions: integration.supportedFeatures,
      supportedTriggers: ['webhook', 'event', 'scheduled'],
      rateLimit: {
        requestsPerSecond: integration.pricing?.limits?.requests_per_minute || 60,
        requestsPerHour: integration.pricing?.limits?.requests_per_hour || 1000,
      },
      requiresAuth: true,
      authType: 'oauth',
      healthStatus: 'healthy',
      lastHealthCheck: new Date(),
      metadata: integration,
    };
  }

  private assessOptimizationRisk(optimizations: any[]): 'low' | 'medium' | 'high' {
    if (optimizations.some(opt => opt.impact === 'high')) {
      return 'medium';
    }
    if (optimizations.some(opt => opt.estimatedImprovement > 50)) {
      return 'medium';
    }
    return 'low';
  }

  private async applyOptimization(workflowId: string, optimization: WorkflowOptimizationResult): Promise<void> {
    // Implementation for applying optimizations
    this.logger.info(`Applying optimization for workflow ${workflowId}`);
    this.emit("optimization-applied", { workflowId, optimization });
  }

  private predictLoad(): number {
    // Simplified load prediction based on historical patterns
    const recentMetrics = this.metrics.slice(-60); // Last hour
    if (recentMetrics.length < 10) return 0;

    const averageLoad = recentMetrics.reduce((sum, m) => sum + m.system.activeExecutions, 0) / recentMetrics.length;
    const trend = recentMetrics.length >= 2 
      ? recentMetrics[recentMetrics.length - 1].system.activeExecutions - recentMetrics[recentMetrics.length - 2].system.activeExecutions
      : 0;

    return Math.max(0, averageLoad + trend * 2); // Simple prediction
  }

  private calculateRecommendedScaling(expectedLoad: number, currentUtilization: number): any {
    const targetUtilization = 0.7; // 70% utilization target
    const currentConcurrency = this.config.maxConcurrentExecutions;
    
    let recommendedConcurrency = currentConcurrency;
    let decision: 'scale_up' | 'scale_down' | 'maintain' = 'maintain';

    if (expectedLoad > currentConcurrency * targetUtilization) {
      recommendedConcurrency = Math.ceil(expectedLoad / targetUtilization);
      decision = 'scale_up';
    } else if (expectedLoad < currentConcurrency * 0.3 && currentConcurrency > 5) {
      recommendedConcurrency = Math.max(5, Math.ceil(expectedLoad / targetUtilization));
      decision = 'scale_down';
    }

    return {
      addExecutors: decision === 'scale_up',
      removeExecutors: decision === 'scale_down',
      targetConcurrency: recommendedConcurrency,
    };
  }

  private identifyPotentialBottlenecks(): string[] {
    const bottlenecks: string[] = [];
    
    // Check integration health
    // Check slow workflows
    // Check high error rates
    // This would analyze actual data
    
    return bottlenecks;
  }

  private generateAlertActions(type: string, category: string, severity: string): any[] {
    const actions = [
      {
        type: 'acknowledge',
        label: 'Acknowledge',
        description: 'Acknowledge the alert',
      }
    ];

    if (severity !== 'critical') {
      actions.push({
        type: 'resolve',
        label: 'Resolve',
        description: 'Mark the alert as resolved',
      });
    }

    if (category === 'integration' && type === 'error') {
      actions.push({
        type: 'auto_fix',
        label: 'Auto-Fix',
        description: 'Attempt automatic resolution',
      });
    }

    return actions;
  }

  private async captureSystemSnapshot(): Promise<OrchestrationSnapshot> {
    const systemHealth = this.workflowEngine.getSystemHealth();
    const integrationHealth = await this.getIntegrationHealth();
    const activeAlerts = this.alerts.filter(alert => !alert.resolved);

    return {
      timestamp: new Date(),
      workflows: {
        total: systemHealth.totalWorkflows,
        active: systemHealth.activeExecutions,
        completed: 0, // Would need to calculate from history
        failed: 0, // Would need to calculate from history
        averageDuration: 0, // Would need to calculate from history
      },
      integrations: {
        total: integrationHealth.totalIntegrations,
        healthy: integrationHealth.healthyIntegrations,
        unhealthy: integrationHealth.totalIntegrations - integrationHealth.healthyIntegrations,
        averageResponseTime: 0, // Would calculate from integration metrics
        totalRequests: 0, // Would calculate from integration metrics
        errorRate: 0, // Would calculate from integration metrics
      },
      system: {
        uptime: Date.now() - this.startTime.getTime(),
        memoryUsage: process.memoryUsage().heapUsed / process.memoryUsage().heapTotal,
        cpuUsage: 0, // Would need actual CPU monitoring
        diskUsage: 0, // Would need actual disk monitoring
        networkLatency: 0, // Would need actual network monitoring
      },
      alerts: {
        active: activeAlerts.length,
        critical: activeAlerts.filter(a => a.severity === 'critical').length,
        warnings: activeAlerts.filter(a => a.severity === 'high' || a.severity === 'medium').length,
        resolved: this.alerts.filter(a => a.resolved).length,
      },
    };
  }

  private async checkSystemHealth(snapshot: OrchestrationSnapshot): Promise<void> {
    // Check for critical issues
    if (snapshot.integrations.unhealthy > snapshot.integrations.total * 0.5) {
      await this.createAlert(
        'critical',
        'system',
        'High Integration Failure Rate',
        `More than 50% of integrations are unhealthy (${snapshot.integrations.unhealthy}/${snapshot.integrations.total})`,
        snapshot,
        'critical'
      );
    }

    if (snapshot.system.memoryUsage > 0.9) {
      await this.createAlert(
        'warning',
        'system',
        'High Memory Usage',
        `Memory usage is at ${(snapshot.system.memoryUsage * 100).toFixed(1)}%`,
        { memoryUsage: snapshot.system.memoryUsage },
        'high'
      );
    }

    if (snapshot.alerts.critical > 5) {
      await this.createAlert(
        'critical',
        'system',
        'Critical Alert Threshold Exceeded',
        `There are ${snapshot.alerts.critical} critical alerts active`,
        { criticalAlerts: snapshot.alerts.critical },
        'critical'
      );
    }
  }

  // Public Utility Methods
  getSystemStatus(): {
    uptime: number;
    version: string;
    components: {
      workflowEngine: boolean;
      workflowService: boolean;
      integrationRegistry: boolean;
    };
    health: {
      overall: 'healthy' | 'degraded' | 'unhealthy';
      score: number;
    };
  } {
    const systemHealth = this.workflowEngine.getSystemHealth();
    const healthScore = systemHealth.registeredAgents > 0 ? 0.9 : 0.5;

    return {
      uptime: Date.now() - this.startTime.getTime(),
      version: '1.0.0',
      components: {
        workflowEngine: true,
        workflowService: true,
        integrationRegistry: true,
      },
      health: {
        overall: healthScore >= 0.8 ? 'healthy' : healthScore >= 0.5 ? 'degraded' : 'unhealthy',
        score: healthScore,
      },
    };
  }

  async shutdown(): Promise<void> {
    this.logger.info("Shutting down Orchestration Manager");

    // Clear timers
    if (this.metricsTimer) clearInterval(this.metricsTimer);
    if (this.optimizationTimer) clearInterval(this.optimizationTimer);
    if (this.healthCheckTimer) clearInterval(this.healthCheckTimer);
    if (this.cleanupTimer) clearInterval(this.cleanupTimer);

    // Shutdown components
    await this.workflowEngine.shutdown();

    this.logger.info("Orchestration Manager shutdown complete");
    this.emit("shutdown-complete");
  }
}