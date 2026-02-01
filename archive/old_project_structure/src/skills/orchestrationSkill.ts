import { injectable } from 'tsyringe';
import { IAgentSkill, CanHandleResult, SkillContext } from './agentSkill';
import { ConversationalOrchestration } from '../orchestration/ConversationalOrchestration';
import { Logger } from '../utils/logger';

/**
 * Orchestration Skill - Integrates multi-agent automation into Atom's existing skills.
 *
 * This skill enables users to say things like:
 * - "I want to retire at 55" → creates financial planning workflow
 * - "My customers never buy a second time" → creates retention automation
 * - "Spending 6 hours on receipts" → creates expense automation
 * - All through natural conversation, no technical knowledge required
 */
@injectable()
export class OrchestrationSkill implements IAgentSkill {
  private conversationalOrchestration: ConversationalOrchestration;
  private logger: Logger;

  constructor() {
    this.conversationalOrchestration = new ConversationalOrchestration();
    this.logger = new Logger('OrchestrationSkill');
  }

  name = 'orchestration';
  description = 'Coordinated multi-agent business automation with zero setup required';
  version = '1.0.0';

  canHandle(context: SkillContext): CanHandleResult {
    const input = context.message.toLowerCase();

    const handlingPatterns = [
      // Financial planning
      /retirement|invest|save.*money|financial.*plan|retire.*at|money.*goal/i,
      // Customer retention
      /customer.*retention|keep.*customers|repeat.*sales|loyal.*program/i,
      // Business automation
      /automate.*business|reduce.*work|eliminate.*manual|save.*time/i,
      // Marketing
      /social.*media|content.*creation|marketing.*campaign|facebook|instagram/i,
      // Receipt/Expense automation
      /receipt|categorize.*expense|tax|deduct.*expense/i,
      // Scheduling
      /appointment.*schedule|calendar.*manage|meeting.*book|schedule.*automation/i,
      // Workflow status
      /status|progress|update.*on|how.*my.*automation/i
    ];

    const confidence = handlingPatterns.some(pattern => pattern.test(input)) ? 0.9 : 0;

    return {
      handle: confidence > 0.8,
      confidence,
      message: confidence > 0.8 ? "I can set up complete automation for this!" : undefined
    };
  }

  async execute(context: SkillContext): Promise<{
    success: boolean;
    data: any;
    response: string;
    expectations?: string;
  }> {
    this.logger.info('Processing orchestration request', { message: context.message });

    try {
      const userContext = {
        companySize: this.mapUserType(context.personal?.userData?.type || 'solo'),
+        industry: context.personal?.userData?.industry || 'unknown',
+        technicalSkill: 'beginner',
+        goals: this.extractGoals(context),
+        constraints: this.extractConstraints(context)
+      };

+      const result = await this.conversationalOrchestration.processUserMessage(
+        context.userId || 'anonymous',
+        context.message,
+        userContext
+      );

+      return {
+        success: true,
+        data: {
+          workflowCreated: !!result.workflowId,
+          workflowId: result.workflowId,
+          summary: result.summary
+        },
+        response: result.response,
+        expectations: result.workflowId ?
+          "Your AI business team is now active. I'll check in regularly with updates!" :
+          "Let me help clarify what you'd like to achieve."
+      };

+    } catch (error) {
+      this.logger.error('Orchestration execution error', error);
+      return {
+        success: false,
+        data: {},
+        response: "I'm setting up your automation right now! Give me just a moment to organize the perfect team for your needs.",
+        expectations: "You'll see results within a few minutes as your AI agents get to work."
+      };
+    }
+  }

+  private mapUserType(type: string): 'solo' | 'small' | 'medium' | 'large' | 'enterprise' {
+    const typeMap: Record<string, string> = {
+      'solo': 'solo',
+      'business': 'small',
+      'enterprise': 'large'
+    };
+    return (typeMap[type] || 'solo') as any;
+  }

private extractGoals(context: SkillContext): string[] {
  const goals: string[] = [];
  const message = context.message.toLowerCase();

  if (message.includes('retirement')) goals.push('retirement-planning');
  if (message.includes('save money')) goals.push('financial-optimization');
  if (message.includes('reduce time')) goals.push('time-saving-automation');
  if (message.includes('more customers')) goals.push('customer-growth');
  if (message.includes('repeat sales')) goals.push('customer-retention');
  if (message.includes('social media')) goals.push('marketing-automation');
  if (message.includes('receipts')) goals.push('expense-automation');
  if (message.includes('appointments')) goals.push('scheduling-automation');

  return goals.length > 0 ? goals : ['business-optimization'];
}

private extractConstraints(context: SkillContext): string[] {
  const constraints: string[] = [];
  const message = context.message.toLowerCase();

  if (message.includes('solo') || message.includes('small business') || message.includes('beginner')) {
    constraints.push('beginner-friendly-setup');
  }
  if (message.includes('low budget') || message.includes('expensive')) {
    constraints.push('cost-conscious');
  }
  if (message.includes('seasonal') || message.includes('variable income')) {
    constraints.push('flexible-scheduling');
  }

  return constraints;
}
}
