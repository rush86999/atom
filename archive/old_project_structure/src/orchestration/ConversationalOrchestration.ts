import { EventEmitter } from 'events';
import { Logger } from '../utils/logger';
import { OrchestrationManager } from './OrchestrationManager';
import { SkillRegistry } from '../skills';
import { IAgentSkill } from '../skills/agentSkill';

interface ConversationContext {
  userMessage: string;
  businessContext?: {
    companySize?: 'solo' | 'small' | 'medium' | 'large' | 'enterprise';
    industry?: string;
    technicalSkill?: 'beginner' | 'intermediate' | 'advanced';
    goals?: string[];
    constraints?: string[];
  };
  preferences?: {
    automationLevel: 'minimal' | 'moderate' | 'full';
    communicationStyle: 'professional' | 'friendly' | 'interactive';
    urgency: 'low' | 'medium' | 'high';
  };
}

interface OrchestrationResponse {
  workflowId: string;
  summary: string;
  agentsAssigned: string[];
  expectedTimeToCompletion: string;
  userNextSteps: string[];
  ongoingMonitoring?: boolean;
}

export class ConversationalOrchestration {
  private logger: Logger;
  private orchestrationManager: OrchestrationManager;
  private skillRegistry: SkillRegistry;
  private conversationHistory: Map<string, ConversationContext[]>;
  private activeWorkflows: Map<string, OrchestrationResponse>;

  constructor() {
    this.logger = new Logger('ConversationalOrchestration');
    this.skillRegistry = new SkillRegistry();
    this.orchestrationManager = new OrchestrationManager(this.skillRegistry, {
+      autoOptimization: true,
+      performanceMonitoring: true,
+      loadBalancing: true
+    });
+
+    this.conversationHistory = new Map();
+    this.activeWorkflows = new Map();
+  }

  async processUserMessage(
+    userId: string,
+    message: string,
+    businessContext?: ConversationContext['businessContext']
+  ): Promise<{
+    response: string;
+    followUpQuestions?: string[];
+    workflowId?: string;
+    summary?: string;
+  }> {
+
+    this.logger.info(`Processing message for user: ${userId}`, { message, businessContext });

+    // Parse the natural language into task type and requirements
+    const parsedIntent = await this.parseUserIntent(message, businessContext);
+
+    if (parsedIntent.type === 'clarification_needed') {
+      return {
+        response: 'I can help with that! Let me understand a bit better. ' + parsedIntent.clarificationQuestion,
+        followUpQuestions: parsedIntent.followUpQuestions
+      };
+    }

+    if (parsedIntent.type === 'workflow_creation') {
+      const workflowResult = await this.createWorkflow(userId, parsedIntent, businessContext);
+      return {
+        response: this.generateFriendlyResponse(workflowResult),
+        workflowId: workflowResult.workflowId,
+        summary: workflowResult.summary
+      };
+    }

+    if (parsedIntent.type === 'status_check') {
+      return this.checkWorkflowStatus(userId, parsedIntent.workflowId);
+    }

+    if (parsedIntent.type === 'modification_request') {
+      return this.modifyExistingWorkflow(userId, parsedIntent);
+    }

+    return {
+      response: "I didn't quite understand that. Here's what I can help with: financial planning, customer automation, marketing, or general business operations. What would you like to focus on?"
+    };
+  }

+  private async parseUserIntent(message: string, context?: ConversationContext['businessContext']) {
+    const lowerMessage = message.toLowerCase();
+
+    // Pattern matching for workflow types
+    const patterns = {
const patterns = {
financial_planning: /retirement|invest|save.*money|financial.*plan|retire.*at|money.*goal/i,
customer_automation: /customer.*retention|keep.*customers|repeat.*sales|loyal.*program/i,
marketing_automation: /social.*media|content.*creation|marketing.*campaign|facebook.*post|instagram/i,
business_automation: /automate|reduce.*work|eliminate.*manual|save.*time|streamline/i,
scheduling: /appointment.*scheduling|calendar.*manage|meeting.*book/i,
receipt_automation: /receipt|categorize.*expense|tax|deduct/i,
workflow_status: /status|progress|how.*going|update/i
};

// Status check requests
if (lowerMessage.includes('status') || lowerMessage.includes('progress') && !lowerMessage.includes('amazing')) {
return { type: 'status_check', workflowId: 'current' };
}

// Determine workflow type
for (const [type, pattern] of Object.entries(patterns)) {
if (pattern.test(lowerMessage)) {
  return {
    type: 'workflow_creation',
    workflowType: type,
    requirements: this.getRequirementsForWorkflow(type, message),
    userIntent: message,
    businessContext: context
  };
}
}

// Default: ask for clarification
return {
type: 'clarification_needed',
workflowType: 'general',
clarificationQuestion: "I'd love to help! Are you looking to automate finances, improve customer retention, save time on manual tasks, or something else?",
followUpQuestions: [
  "What's your biggest time drain currently?",
  "Are you a solo business or have employees?",
  "What's your main business goal right now?"
]
};
}

private getRequirementsForWorkflow(type: string, message: string): string[] {
const requirementMap: Record<string, string[]> = {
financial_planning: ['financial-analysis', 'tax-optimization', 'retirement-planning'],
customer_automation: ['customer-segmentation', 'retention-strategies', 'crm-integration'],
marketing_automation: ['content-creation', 'social-media-automation', 'lead-generation'],
business_automation: ['process-automation', 'workflow-optimization', 'time-saving'],
scheduling: ['calendar-integration', 'appointment-booking', 'customer-communications'],
receipt_automation: ['expense-tracking', 'tax-categorization', 'report-generation']
};

return requirementMap[type] || ['business-optimization', 'automation', 'efficiency'];
}

private async createWorkflow(userId: string, parsedIntent: any, businessContext?: any): Promise<OrchestrationResponse> {
const workflowId = await this.orchestrationManager.submitWorkflow({
type: this.mapWorkflowType(parsedIntent.workflowType),
description: parsedIntent.userIntent,
requirements: parsedIntent.requirements,
priority: 8,
businessContext: businessContext || {
+        companySize: 'solo',
+        technicalSkill: 'beginner',
+        goals: ['time-saving', 'automation', 'growth']
+      }
+    });

const response: OrchestrationResponse = {
+      workflowId,
+      summary: `I'm setting up your complete automation system. This will save you ${this.estimateTimeSaved(parsedIntent.workflowType)} per week!`,
+      agentsAssigned: ['Personal Finance Advisor', 'Operations Manager', 'Analytics Officer'],
+      expectedTimeToCompletion: '2-3 minutes',
+      userNextSteps: [
+        'You can continue chatting with me while your automation runs',
+        'I\'ll provide regular updates on progress',
+        'Everything is hands-off from your side'
+      ],
+      ongoingMonitoring: true
+    };

+    // Store the workflow
+    this.activeWorkflows.set(workflowId, response);

+    return response;
}

private mapWorkflowType(inputType: string): string {
const typeMap: Record<string, string> = {
+      financial_planning: 'financial-planning',
+      customer_automation: 'customer-automation',
+      marketing_automation: 'marketing-automation',
+      business_automation: 'business-automation',
+      scheduling: 'scheduling-management',
+      receipt_automation: 'expense-automation'
};
+    return typeMap[inputType] || 'business-automation';
}

private estimateTimeSaved(type: string): string {
const savingsMap: Record<string, string> = {
+      financial_planning: '4-6 hours',
+      customer_automation: '6-8 hours',
+      marketing_automation: '4-6 hours',
+      business_automation: '8-12 hours',
+      scheduling: '2-4 hours',
+      receipt_automation: '3-5 hours'
};
+    return savingsMap[type] || 'several hours';
}

private generateFriendlyResponse(result: OrchestrationResponse): string {
return `Perfect! I've created your automation system with workflow ID: ${result.workflowId}

${result.summary}

Your assigned AI team includes: ${result.agentsAssigned.join(', ')}.

⏱️ Expected setup time: ${result.expectedTimeToCompletion}
✅ What's next: ${result.userNextSteps[0]}

Just check back with me whenever you want updates - I'll handle everything automatically!`;
}

private checkWorkflowStatus(userId: string, workflowId: string) {
return {
+      response

// Determine workflow type
for (const [type, pattern] of Object.entries(patterns)) {
if (pattern.test(lowerMessage)) {
  return {
    type: 'workflow_creation',
    workflowType: type,
    requirements: this.getRequirementsForWorkflow(type, message),
    userIntent: message
  };
}
}

  private checkWorkflowStatus(userId: string, workflowId: string) {
    try {
      const status = this.orchestrationManager.getWorkflowStatus(workflowId);
      if (status.status === 'completed') {
        return {
          response: `Great news! Your workflow ${workflowId} is complete! 🎉 You'll start seeing the benefits immediately. Want to discuss next steps or ask about anything else?`
        };
      } else if (status.status === 'running') {
        return {
          response: `Your workflow ${workflowId} is actively running with ${status.progress.toFixed(0)}% complete. Everything is processing smoothly - I'll let you know as soon as it's ready!`
        };
      } else if (status.status === 'pending') {
        return {
          response: `Your workflow ${workflowId} is queued and will start shortly. The system is optimizing the best agent assignments for your specific needs.`
        };
      }
    } catch (error) {
      return {
        response: "Let me check on that for you. Your automation should be working in the background. Is there something specific you'd like me to help with instead?"
      };
    }
    return { response: "I'd be happy to help! What would you like assistance with today?" };
  }

  private modifyExistingWorkflow(userId: string, modification: any) {
    return {
      response: "Let me adjust your automation to better fit your needs. Would you like me to make it more aggressive, more conservative, or change the focus entirely?"
    };
  }
}

// Default: ask for clarification
return {
type: 'clarification_needed',
workflowType: 'general',
clarificationQuestion: "I'd love to help! Are you looking to automate finances, improve customer retention, save time on manual tasks, or something else?",
followUpQuestions: [
  "What's your biggest time drain currently?",
  "What's your main business goal - growth, automation, or savings?",
  "How tech-savvy would you say you are?"
]
};
+      const workflowIdMatch = message.match(/\bwf_[a-zA-Z0-9]+\b/) || message.match(/#([a
