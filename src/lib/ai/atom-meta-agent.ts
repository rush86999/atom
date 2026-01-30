/**
 * Atom Meta-Agent
 * Ported from Atom's backend/core/atom_meta_agent.py
 * The master orchestration agent that coordinates all other agents
 */

import { LLMRouter } from './llm-router';
import { AgentGovernanceService } from './agent-governance';
import { IntelligentAgentCoordinator } from './intelligent-agent-coordinator';
import { getDatabase } from '../database';

interface AgentCapability {
    id: string;
    name: string;
    description: string;
    category: 'crm' | 'communication' | 'productivity' | 'finance' | 'ecommerce' | 'development';
    actions: string[];
}

interface TaskPlan {
    steps: {
        agentId: string;
        action: string;
        parameters: Record<string, unknown>;
        dependsOn: number[];
    }[];
    estimatedDuration: number;
    requiredIntegrations: string[];
}

interface ExecutionResult {
    success: boolean;
    results: { step: number; output: unknown; error?: string }[];
    summary: string;
}

export class AtomMetaAgent {
    private tenantId: string;
    private userId: string;
    private llmRouter: LLMRouter;
    private governance: AgentGovernanceService;
    private coordinator: IntelligentAgentCoordinator;

    // Available agent capabilities
    private capabilities: AgentCapability[] = [
        {
            id: 'shopify_agent',
            name: 'Shopify Agent',
            description: 'E-commerce store management, orders, inventory',
            category: 'ecommerce',
            actions: ['check_inventory', 'process_orders', 'update_products', 'analyze_sales', 'fulfill_orders'],
        },
        {
            id: 'crm_agent',
            name: 'CRM Agent',
            description: 'Customer relationship management across Salesforce, HubSpot',
            category: 'crm',
            actions: ['search_contacts', 'create_lead', 'update_deal', 'log_activity', 'get_pipeline'],
        },
        {
            id: 'calendar_agent',
            name: 'Calendar Agent',
            description: 'Schedule management, meeting coordination',
            category: 'productivity',
            actions: ['check_availability', 'schedule_meeting', 'reschedule', 'find_free_slots', 'send_invite'],
        },
        {
            id: 'email_agent',
            name: 'Email Agent',
            description: 'Email composition, search, and automation',
            category: 'communication',
            actions: ['search_emails', 'send_email', 'draft_reply', 'summarize_thread', 'create_template'],
        },
        {
            id: 'project_agent',
            name: 'Project Agent',
            description: 'Task and project management across Jira, Asana, Trello',
            category: 'productivity',
            actions: ['create_task', 'update_status', 'assign_task', 'get_sprint', 'log_time'],
        },
        {
            id: 'finance_agent',
            name: 'Finance Agent',
            description: 'Accounting, invoicing, financial analysis',
            category: 'finance',
            actions: ['categorize_transactions', 'generate_report', 'reconcile_accounts', 'create_invoice', 'forecast'],
        },
        {
            id: 'dev_agent',
            name: 'Developer Agent',
            description: 'Code repository management, PR reviews, deployments',
            category: 'development',
            actions: ['list_prs', 'create_issue', 'review_code', 'merge_pr', 'deploy'],
        },
        {
            id: 'browser_agent',
            name: 'Browser Agent',
            description: 'Web automation, data extraction, form filling',
            category: 'productivity',
            actions: ['navigate', 'click', 'type', 'screenshot', 'extract_data'],
        },
        {
            id: 'meta_evolution_agent',
            name: 'Self-Evolution Agent',
            description: 'Dynamic capability creation and tool synthesis',
            category: 'development',
            actions: ['register_skill', 'synthesize_skill', 'extract_formula'],
        },
    ];

    constructor(tenantId: string, userId: string) {
        this.tenantId = tenantId;
        this.userId = userId;
        this.llmRouter = new LLMRouter(getDatabase());
        this.governance = new AgentGovernanceService(getDatabase());
        this.coordinator = new IntelligentAgentCoordinator();
    }

    /**
     * Understand user intent and plan execution
     */
    async understand(userRequest: string): Promise<{
        intent: string;
        entities: Record<string, unknown>;
        suggestedPlan: TaskPlan;
        clarificationNeeded?: string;
    }> {
        const prompt = `You are Atom, an AI assistant that orchestrates multiple specialized agents.

Available agents and their capabilities:
${this.capabilities.map((c) => `- ${c.name} (${c.id}): ${c.description}\n  Actions: ${c.actions.join(', ')}`).join('\n')}

User request: "${userRequest}"

Analyze the request and respond with JSON:
{
  "intent": "brief description of what user wants",
  "entities": { extracted entities like names, dates, amounts },
  "steps": [
    { "agentId": "...", "action": "...", "parameters": {...}, "dependsOn": [] }
  ],
  "requiredIntegrations": ["shopify", "gmail", etc],
  "clarificationNeeded": null or "question if ambiguous",
  "missingCapabilities": ["List any actions required for the task that are NOT in the available actions above"]
}

If you identify missing capabilities, include a step for "meta_evolution_agent" with action "synthesize_skill" to bridge the gap.

JSON:`;

        const response = await this.llmRouter.call(this.tenantId, {
            type: 'analysis',
            messages: [{ role: 'user', content: prompt }],
            model: 'gpt-4o',
        });

        try {
            const jsonMatch = response.content?.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const parsed = JSON.parse(jsonMatch[0]);
                return {
                    intent: parsed.intent || 'Unknown intent',
                    entities: parsed.entities || {},
                    suggestedPlan: {
                        steps: parsed.steps || [],
                        estimatedDuration: parsed.steps?.length * 5 || 0, // 5s per step estimate
                        requiredIntegrations: parsed.requiredIntegrations || [],
                    },
                    clarificationNeeded: parsed.clarificationNeeded,
                };
            }
        } catch (error) {
            console.error('Meta-agent understand error:', error);
        }

        return {
            intent: 'Unable to understand request',
            entities: {},
            suggestedPlan: { steps: [], estimatedDuration: 0, requiredIntegrations: [] },
            clarificationNeeded: 'Could you please rephrase your request?',
        };
    }

    /**
     * Execute a planned task
     */
    async execute(plan: TaskPlan, dryRun = false): Promise<ExecutionResult> {
        const results: ExecutionResult['results'] = [];
        const stepOutputs: Map<number, unknown> = new Map();

        for (let i = 0; i < plan.steps.length; i++) {
            const step = plan.steps[i];

            // Check dependencies
            for (const depIndex of step.dependsOn) {
                const depResult = results.find((r) => r.step === depIndex);
                if (depResult?.error) {
                    results.push({
                        step: i,
                        output: null,
                        error: `Dependency step ${depIndex} failed`,
                    });
                    continue;
                }
            }

            // Check governance
            const canProceed = await this.governance.canPerformAction(
                this.tenantId,
                step.agentId,
                step.action
            );

            if (!canProceed.allowed) {
                results.push({
                    step: i,
                    output: null,
                    error: `Governance denied: ${canProceed.reason}`,
                });
                continue;
            }

            if (dryRun) {
                results.push({
                    step: i,
                    output: { dryRun: true, wouldExecute: `${step.agentId}.${step.action}` },
                });
                continue;
            }

            // Execute step
            try {
                const output = await this.executeStep(step, stepOutputs);
                stepOutputs.set(i, output);
                results.push({ step: i, output });
            } catch (error) {
                results.push({
                    step: i,
                    output: null,
                    error: (error as Error).message,
                });
            }
        }

        const successCount = results.filter((r) => !r.error).length;
        const summary = `Executed ${successCount}/${plan.steps.length} steps successfully.`;

        return {
            success: successCount === plan.steps.length,
            results,
            summary,
        };
    }

    /**
     * Execute a single step
     */
    private async executeStep(
        step: TaskPlan['steps'][0],
        previousOutputs: Map<number, unknown>
    ): Promise<unknown> {
        // Resolve any references to previous step outputs
        const params = { ...step.parameters };
        for (const [key, value] of Object.entries(params)) {
            if (typeof value === 'string' && value.startsWith('$step')) {
                const stepIndex = parseInt(value.replace('$step', ''));
                params[key] = previousOutputs.get(stepIndex);
            }
        }

        // For now, return a simulated response
        // In production, this would dispatch to the actual agent
        return {
            agent: step.agentId,
            action: step.action,
            parameters: params,
            result: 'Simulated success',
            timestamp: new Date().toISOString(),
        };
    }

    /**
     * Natural language interface - understand and execute
     */
    async chat(message: string): Promise<{
        response: string;
        plan?: TaskPlan;
        executed?: boolean;
        results?: ExecutionResult;
    }> {
        // First, understand the request
        const understanding = await this.understand(message);

        // If clarification needed, ask
        if (understanding.clarificationNeeded) {
            return {
                response: understanding.clarificationNeeded,
            };
        }

        // If simple query, respond directly
        if (understanding.suggestedPlan.steps.length === 0) {
            return {
                response: `I understood: ${understanding.intent}. However, I don't have a specific action to take. How can I help further?`,
            };
        }

        // For complex tasks, show plan and ask for confirmation
        const planSummary = understanding.suggestedPlan.steps
            .map((s, i) => `${i + 1}. ${s.agentId}: ${s.action}`)
            .join('\n');

        return {
            response: `I'll help you with: **${understanding.intent}**\n\nHere's my plan:\n${planSummary}\n\nShall I proceed?`,
            plan: understanding.suggestedPlan,
            executed: false,
        };
    }

    /**
     * Get available capabilities
     */
    getCapabilities(): AgentCapability[] {
        return this.capabilities;
    }
}

export default AtomMetaAgent;
