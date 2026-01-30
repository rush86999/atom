/**
 * AI Workflow Optimizer
 * Ported from Atom's backend/core/ai_workflow_optimizer.py
 * Uses AI to suggest and optimize workflow automations
 */

import { LLMRouter } from './llm-router';
import { getDatabase } from '../database';

interface WorkflowStep {
    id: string;
    type: 'trigger' | 'action' | 'condition' | 'loop';
    name: string;
    config: Record<string, unknown>;
}

interface WorkflowAnalysis {
    efficiency: number; // 0-100
    bottlenecks: { stepId: string; issue: string; impact: 'low' | 'medium' | 'high' }[];
    suggestions: { type: 'add' | 'remove' | 'modify'; stepId?: string; description: string; benefit: string }[];
    estimatedTimeSaved: number; // minutes per execution
}

interface WorkflowTemplate {
    id: string;
    name: string;
    description: string;
    category: string;
    steps: WorkflowStep[];
    requiredIntegrations: string[];
    popularity: number;
}

export class AIWorkflowOptimizer {
    private tenantId: string;
    private llmRouter: LLMRouter;

    constructor(tenantId: string) {
        this.tenantId = tenantId;
        this.llmRouter = new LLMRouter(getDatabase());
    }

    /**
     * Analyze an existing workflow for optimization opportunities
     */
    async analyzeWorkflow(steps: WorkflowStep[]): Promise<WorkflowAnalysis> {
        const prompt = `Analyze this workflow for optimization opportunities:

Workflow steps:
${steps.map((s, i) => `${i + 1}. [${s.type}] ${s.name} - Config: ${JSON.stringify(s.config)}`).join('\n')}

Evaluate:
1. Efficiency score (0-100)
2. Identify bottlenecks
3. Suggest improvements

Respond with JSON:
{
  "efficiency": 75,
  "bottlenecks": [{"stepId": "...", "issue": "...", "impact": "medium"}],
  "suggestions": [{"type": "modify", "stepId": "...", "description": "...", "benefit": "..."}],
  "estimatedTimeSaved": 5
}

JSON:`;

        const response = await this.llmRouter.call(this.tenantId, {
            type: 'analysis',
            messages: [{ role: 'user', content: prompt }],
            model: 'gpt-4o-mini',
        });

        try {
            const jsonMatch = response.content?.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                return JSON.parse(jsonMatch[0]);
            }
        } catch (error) {
            console.error('Workflow analysis error:', error);
        }

        return {
            efficiency: 50,
            bottlenecks: [],
            suggestions: [],
            estimatedTimeSaved: 0,
        };
    }

    /**
     * Generate workflow from natural language description
     */
    async generateWorkflow(description: string): Promise<{
        workflow: WorkflowStep[];
        explanation: string;
        requiredIntegrations: string[];
    }> {
        const prompt = `Generate a workflow automation based on this description:

"${description}"

Available triggers: webhook, schedule, email_received, new_record, file_uploaded
Available actions: send_email, create_record, update_record, send_slack, call_api, run_script
Available conditions: if_contains, if_equals, if_greater_than, if_empty

Respond with JSON:
{
  "workflow": [
    {"id": "step1", "type": "trigger", "name": "...", "config": {...}},
    {"id": "step2", "type": "action", "name": "...", "config": {...}}
  ],
  "explanation": "Brief explanation of what this workflow does",
  "requiredIntegrations": ["gmail", "slack", etc]
}

JSON:`;

        const response = await this.llmRouter.call(this.tenantId, {
            type: 'creative',
            messages: [{ role: 'user', content: prompt }],
            model: 'gpt-4o',
        });

        try {
            const jsonMatch = response.content?.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const parsed = JSON.parse(jsonMatch[0]);
                return {
                    workflow: parsed.workflow || [],
                    explanation: parsed.explanation || '',
                    requiredIntegrations: parsed.requiredIntegrations || [],
                };
            }
        } catch (error) {
            console.error('Workflow generation error:', error);
        }

        return {
            workflow: [],
            explanation: 'Unable to generate workflow. Please provide more details.',
            requiredIntegrations: [],
        };
    }

    /**
     * Suggest workflow templates based on connected integrations
     */
    async suggestTemplates(connectedIntegrations: string[]): Promise<WorkflowTemplate[]> {
        const templates: WorkflowTemplate[] = [
            {
                id: 'new-customer-welcome',
                name: 'New Customer Welcome Sequence',
                description: 'Sends welcome email and Slack notification when new customer is added',
                category: 'onboarding',
                requiredIntegrations: ['gmail', 'slack', 'hubspot'],
                popularity: 95,
                steps: [
                    { id: '1', type: 'trigger', name: 'New HubSpot Contact', config: { source: 'hubspot' } },
                    { id: '2', type: 'action', name: 'Send Welcome Email', config: { template: 'welcome' } },
                    { id: '3', type: 'action', name: 'Notify Team on Slack', config: { channel: 'sales' } },
                ],
            },
            {
                id: 'low-inventory-alert',
                name: 'Low Inventory Alert',
                description: 'Monitors Shopify inventory and sends alerts when stock is low',
                category: 'ecommerce',
                requiredIntegrations: ['shopify', 'slack'],
                popularity: 88,
                steps: [
                    { id: '1', type: 'trigger', name: 'Schedule Check', config: { cron: '0 9 * * *' } },
                    { id: '2', type: 'action', name: 'Check Shopify Inventory', config: { threshold: 10 } },
                    { id: '3', type: 'condition', name: 'If Low Stock', config: { operator: 'less_than', value: 10 } },
                    { id: '4', type: 'action', name: 'Alert on Slack', config: { channel: 'inventory' } },
                ],
            },
            {
                id: 'lead-follow-up',
                name: 'Automated Lead Follow-up',
                description: 'Sends follow-up emails to leads who haven\'t responded',
                category: 'sales',
                requiredIntegrations: ['salesforce', 'gmail'],
                popularity: 92,
                steps: [
                    { id: '1', type: 'trigger', name: 'Daily Check', config: { cron: '0 10 * * 1-5' } },
                    { id: '2', type: 'action', name: 'Get Stale Leads', config: { daysInactive: 3 } },
                    { id: '3', type: 'loop', name: 'For Each Lead', config: {} },
                    { id: '4', type: 'action', name: 'Send Follow-up Email', config: { template: 'follow-up' } },
                ],
            },
            {
                id: 'invoice-reminder',
                name: 'Invoice Payment Reminder',
                description: 'Sends reminders for overdue invoices',
                category: 'finance',
                requiredIntegrations: ['quickbooks', 'gmail'],
                popularity: 85,
                steps: [
                    { id: '1', type: 'trigger', name: 'Daily Check', config: { cron: '0 9 * * *' } },
                    { id: '2', type: 'action', name: 'Get Overdue Invoices', config: { daysOverdue: 7 } },
                    { id: '3', type: 'action', name: 'Send Reminder Email', config: { template: 'invoice-reminder' } },
                ],
            },
            {
                id: 'github-pr-notification',
                name: 'PR Notification to Slack',
                description: 'Notifies team when new PR is opened',
                category: 'development',
                requiredIntegrations: ['github', 'slack'],
                popularity: 90,
                steps: [
                    { id: '1', type: 'trigger', name: 'New PR Opened', config: { event: 'pull_request.opened' } },
                    { id: '2', type: 'action', name: 'Post to Slack', config: { channel: 'dev-team' } },
                ],
            },
            {
                id: 'meeting-prep',
                name: 'Meeting Preparation Assistant',
                description: 'Sends briefing docs before scheduled meetings',
                category: 'productivity',
                requiredIntegrations: ['google_calendar', 'gmail', 'notion'],
                popularity: 78,
                steps: [
                    { id: '1', type: 'trigger', name: 'Meeting in 1 Hour', config: { offset: -60 } },
                    { id: '2', type: 'action', name: 'Gather Context from Notion', config: {} },
                    { id: '3', type: 'action', name: 'Send Briefing Email', config: {} },
                ],
            },
        ];

        // Filter templates by connected integrations
        return templates.filter((template) =>
            template.requiredIntegrations.some((req) => connectedIntegrations.includes(req))
        ).sort((a, b) => b.popularity - a.popularity);
    }

    /**
     * Learn from user behavior to suggest automations
     */
    async suggestAutomations(
        recentActions: { action: string; target: string; timestamp: string }[]
    ): Promise<{ suggestion: string; trigger: string; actions: string[]; confidence: number }[]> {
        // Find patterns in recent actions
        const actionCounts: Record<string, number> = {};
        const sequences: string[][] = [];

        for (let i = 0; i < recentActions.length - 1; i++) {
            const current = `${recentActions[i].action}:${recentActions[i].target}`;
            const next = `${recentActions[i + 1].action}:${recentActions[i + 1].target}`;

            const sequence = `${current} -> ${next}`;
            actionCounts[sequence] = (actionCounts[sequence] || 0) + 1;
        }

        // Find frequent patterns
        const suggestions: { suggestion: string; trigger: string; actions: string[]; confidence: number }[] = [];

        for (const [sequence, count] of Object.entries(actionCounts)) {
            if (count >= 3) {
                const [trigger, action] = sequence.split(' -> ');
                suggestions.push({
                    suggestion: `Automate: When you ${trigger}, automatically ${action}`,
                    trigger,
                    actions: [action],
                    confidence: Math.min(count / 10, 1),
                });
            }
        }

        return suggestions.sort((a, b) => b.confidence - a.confidence).slice(0, 5);
    }
}

export default AIWorkflowOptimizer;
