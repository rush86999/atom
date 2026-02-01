import { EventEmitter } from "events";
import { Logger } from "../utils/logger";
import { OrchestrationEngine } from "./OrchestrationEngine";
import { AgentRegistry } from "./AgentRegistry";

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
    this.logger = new Logger("OptimizationManager");
    this.engine = engine;
    this.agentRegistry = agentRegistry;
    this.config = config;

    this.initializeOptimizationRules();
  }

  private initializeOptimizationRules(): void {
    this.logger.info("Initializing optimization rules");

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
        return ["Reduced max concurrent agents"];
      },
      priority: 9,
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
        return ["Increased max concurrent agents"];
      },
      priority: 7,
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
        return ["Enhanced fallback strategy", "Increased retry attempts"];
      },
      priority: 10,
    });

    // Cost optimization rules
    this.addRule({
      id: 'enable-resource-conservation',
      name: 'Enable resource conservation mode',
      type: 'cost',
      condition: (metrics) => metrics.queueLength === 0 && metrics.successRate === 1,
      action: async (system) => {
        system.engine.setConfig({ maxConcurrentAgents: 1 });
        return ["Conserving resources in idle state"];
      },
      priority: 6,
    });

    // Agent pool optimization
    this.addRule({
      id: 'rebalance-agents',
      name: 'Rebalance agent load based on performance',
      type: 'resource',
      condition: (metrics) => true, // Always check for rebalancing
      action: async (system) => {
        const improvements = await this.rebalanceAgentPool();
        return improvements;
      },
      priority: 5,
    });
  }

+  addRule(rule: OptimizationRule): void {
+    this.rules.push(rule);
+    this.rules.sort((a, b) => b.priority - a.priority);
+  }

  async performAutoOptimization(): Promise<OptimizationResult[]> {
    this.logger.info("Starting automatic optimization");
    const results: OptimizationResult[] = [];
    const metrics = this.engine.getSystemHealth();

    for (const rule of this.rules) {
      try {
        if (rule.condition(metrics)) {
          this.logger.debug(`Triggering optimization rule: ${rule.name}`);

          const improvements = await rule.action({
            engine: this.engine,
            registry: this.agentRegistry,
            metrics: metrics,
          });

          const result: OptimizationResult = {
            ruleId: rule.id,
            success: true,
            improvements,
            newConfig: this.engine.getConfig(),
            timestamp: new Date(),
          };

          this.optimizationHistory.push(result);
          results.push(result);

          this.logger.info(
            `Optimization completed: ${rule.name} - ${improvements.join(", ")}`,
          );
          this.emit("optimization-completed", result);
        }
      } catch (error) {
        this.logger.error(`Optimization rule ${rule.name} failed:`, error);

        const result: OptimizationResult = {
          ruleId: rule.id,
          success: false,
          improvements: [],
          newConfig: this.engine.getConfig(),
          timestamp: new Date(),
        };

        this.optimizationHistory.push(result);
        results.push(result);
        this.emit("optimization-failed", { rule, error, result });
      }
    }

    return results;
  }

  async triggerOptimization(): Promise<void> {
    this.logger.info("Manual optimization triggered");
    await this.performAutoOptimization();
  }

  async rebalanceAgentPool(): Promise<string[]> {
    const improvements: string[] = [];
    const agentHealth = this.agentRegistry.getAgentHealthStatus();

    // Identify overloaded agents
    const overloadedAgents = Object.values(agentHealth).filter(
      (agent) => agent.status === "critical",
    );

    if (overloadedAgents.length > 0) {
      improvements.push(
        `Rebalancing ${overloadedAgents.length} critical agents`,
      );

      // Implement agent rebalancing logic here
      // This could involve redistributing tasks, adjusting priorities, etc.
      for (const agent of overloadedAgents) {
        this.logger.warn(`Agent ${agent.name} is critical, rebalancing load`);
        // Add specific rebalancing actions
      }
    }

    return improvements;
  }

  getOptimizationHistory(): OptimizationResult[] {
    return [...this.optimizationHistory];
  }

  clearHistory(): void {
    this.optimizationHistory = [];
    this.logger.info("Optimization history cleared");
  }

  getMetrics(): any {
    return {
      totalOptimizations: this.optimizationHistory.length,
      successfulOptimizations: this.optimizationHistory.filter(
        (r) => r.success,
      ).length,
      failedOptimizations: this.optimizationHistory.filter(
        (r) => !r.success,
      ).length,
      successRate:
        this.optimizationHistory.length > 0
          ? this.optimizationHistory.filter((r) => r.success).length /
            this.optimizationHistory.length
          : 0,
      lastOptimization: this.optimizationHistory[
        this.optimizationHistory.length - 1
      ],
      recentImprovements: this.optimizationHistory
        .slice(-5)
        .flatMap((r) => r.improvements),
    };
  }

  stop(): void {
    this.logger.info("Optimization manager stopped");
    this.removeAllListeners();
  }

  start(): void {
    this.logger.info("Optimization manager started");
    // Could implement periodic optimization scheduling here
  }

  exportConfig(): any {
    return {
      rules: this.rules.map((r) => ({
        id: r.id,
        name: r.name,
        type: r.type,
        priority: r.priority,
      })),
      currentConfig: this.config,
      optimizationMetrics: this.getMetrics(),
    };
  }
}
