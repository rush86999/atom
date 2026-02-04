import { AutonomousWorkflowIntegration } from './AutonomousWorkflowIntegration';
import { EnhancedAutonomousTriggers } from './EnhancedAutonomousTriggers';
import { AutonomousWebhookMonitor } from './AutonomousWebhookMonitor';
import { VisualScreenAnalyzer } from './visualScreenAnalyzer';
import { AutonomousTestRunner } from './autonomousTestRunner';

// Main entry point for autonomous workflow features
export class AutonomousWorkflowSystem {
  private integration: AutonomousWorkflowIntegration;
  private initialized = false;

  constructor() {
    this.integration = new AutonomousWorkflowIntegration();
  }

  async initialize(): Promise<void> {
    if (this.initialized) return;

    await this.integration.initialize();
    this.initialized = true;
    console.log('🤖 Autonomous Workflow System initialized');
  }

  async shutdown(): Promise<void> {
    if (!this.initialized) return;

    await this.integration.shutdown();
    this.initialized = false;
  }

  // Main methods for autonomous features
  async registerWorkflow(workflowData: any): Promise<string> {
    return this.integration.registerExistingWorkflow(workflowData);
  }

  async monitorWebhooks(workflowId: string, config: any): Promise<void> {
    return this.integration.addSmartMonitoring(workflowId, config);
  }

  async getPredictiveInsights(workflowId: string): Promise<any> {
    return this.integration.getPredictiveInsights(workflowId);
  }

  async optimizeSchedule(workflowId: string): Promise<void> {
    return this.integration.optimizeSchedule(workflowId);
  }
}

// Export all components for use
export * from './AutonomousWorkflowIntegration';
export * from './EnhancedAutonomousTriggers';
export * from './AutonomousWebhookMonitor';
export * from './visualScreenAnalyzer';
export * from './autonomousTestRunner';

// Default export for easy import
export default AutonomousWorkflowSystem;
