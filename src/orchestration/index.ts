export { OrchestrationEngine } from './OrchestrationEngine';
export { AgentRegistry } from './AgentRegistry';
export { OrchestrationManager, type WorkflowRequest, type SystemMetrics } from './OrchestrationManager';
export { MetricsCollector } from './MetricsCollector';
export { OptimizationManager } from './OptimizationManager';
export { FinancialPlanningWorkflow } from './workflows/FinancialPlanningWorkflow';
export { exampleRunner } from './examples/FinancialPlanningExample';

// Convenience initialization function
export function createOrchestrationSystem(config: {
  autoOptimization?: boolean;
  performanceMonitoring?: boolean;
  loadBalancing?: boolean;
  maxConcurrentAgents?: number;
}) {
  const defaultConfig = {
    autoOptimization: true,
    performanceMonitoring: true,
    loadBalancing: true,
    maxConcurrentAgents: 5
  };

  const { OrchestrationManager } = require('./OrchestrationManager');
  const { SkillRegistry } = require('../skills');

  const skillRegistry = new SkillRegistry();
  return new OrchestrationManager(skillRegistry, { ...defaultConfig, ...config });
}
