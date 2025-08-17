import { EventEmitter } from 'events';
import { Logger } from '../utils/logger';
import { OrchestrationEngine } from './OrchestrationEngine';
import { AgentRegistry } from './AgentRegistry';

export interface OptimizationRule {
  id: string;
  name: string;
  type: 'performance' | 'reliability' | 'cost' | 'resource';
  condition: (metrics: any) => boolean;
  action: (system: any) => Promise<void>;
  priority: number;
}

export interface OptimizationResult {
  ruleId: string;
  success: boolean;
  improvements: string[];
  newConfig: any;
  timestamp: Date;
}

export class OptimizationManager extends EventEmitter {
  private logger: Logger;
  private engine: OrchestrationEngine;
  private agentRegistry: AgentRegistry;
  private rules: OptimizationRule[] = [];
  private optimizationHistory: OptimizationResult[] = [];
  private config: any;

  constructor(engine: OrchestrationEngine, agentRegistry: AgentRegistry, config: any = {}) {
    super();
    this.logger = new Logger('OptimizationManager');
+    this.engine = engine;
+    this.agentRegistry = agentRegistry;
+    this.config = config;

    this.initializeOptimizationRules();
+  }

  private initializeOptimizationRules(): void {
    this.logger.info('Initializing optimization rules');

    // Performance optimization rules
    this.addRule({
      id: 'reduce-concurrency',
      name: 'Reduce concurrent agents under high load',
      type: 'performance',
      condition: (metrics) => metrics.successRate < 0.8,
      action: async (system) => {
        const currentLimit = system.engine.getConfig('maxConcurrentAgents');
        const newLimit = Math.max(1, Math.floor(currentLimit * 0.8));
        system.engine.setConfig({ maxConcurrentAgents: newLimit });
        return ['Reduced max concurrent agents'];
      },
      priority: 9
    });

    this.addRule({
      id: 'increase-concurrency',
      name: 'Increase concurrent agents under low load',
      type: 'performance',
      condition: (metrics) => metrics.successRate > 0.95 && metrics.queueLength > 5,
      action: async (system) => {
        const currentLimit = system.engine.getConfig('maxConcurrentAgents');
        const newLimit = Math.min(10, Math.ceil(currentLimit * 1.2));
        system.engine.setConfig({ maxConcurrentAgents: newLimit });
        return ['Increased max concurrent agents'];
      },
      priority: 7
    });

    // Reliability optimization rules
    this.addRule({
      id: 'strengthen-fallback',
      name: 'Strengthen fallback strategy on failure',
      type: 'reliability',
      condition: (metrics) => metrics.failedTasks > metrics.totalTasks * 0.3,
      action: async (system) => {
        system.engine.setConfig({
+          recoveryMode: 'failover',
+          retryAttempts: 5,
+          delegationConfidenceThreshold: 0.5
+        });
+        return ['Enhanced fallback strategy', 'Increased retry attempts'];
+      },
+      priority: 10
    });

    // Cost optimization rules
    this.addRule({
      id: 'enable-resource-conservation',
      name: 'Enable resource conservation mode',
      type: 'cost',
      condition: (metrics) => metrics.queueLength === 0 && metrics.successRate === 1,
      action: async (system) => {
        system.engine.setConfig({ maxConcurrentAgents: 1 });
        return ['Conserving resources in idle state'];
      },
+      priority: 6
    });

    // Agent pool optimization
    this.addRule({
      id: 'rebalance-agents',
      name: 'Rebalance agent load based on performance',
      type: 'resource',
      condition: (metrics) => true, // Always check for rebalancing
      action: async (system) => {
        const improvements = await this.rebalanceAgentPool();
+        return improvements;
      },
+      priority: 5
+    });
+  }

+  addRule(rule: OptimizationRule): void {
+    this.rules.push(rule);
+    this.rules.sort((a, b) => b.priority - a.priority);
+  }

+  async performAutoOptimization(): Promise<OptimizationResult[]> {
+    this.logger.info('Starting automatic optimization');
+    const results: OptimizationResult[] = [];
+    const metrics = this.engine.getSystemHealth();

    for (const rule of this.rules) {
+      try {
+        if (rule.condition(metrics)) {
+          this.logger.debug(`Triggering optimization rule: ${rule.name}`);
+
+          const initialConfig = this.engine.getConfig();
+          await rule.action({
+            engine: this.engine,
+            registry: this.agentRegistry,
+            metrics: metrics
+          });

          const
