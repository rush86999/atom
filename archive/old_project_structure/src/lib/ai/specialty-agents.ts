import { DatabaseService } from '../database'
import { SkillRegistryService, AgentSkillSubscription } from './skill-registry'

export interface SpecialtyAgent {
    id: string
    name: string
    category: string
    description: string
    capabilities: string[]
    moduleClass: string
    status: 'student' | 'intern' | 'supervised' | 'autonomous'
    confidenceScore: number
    skills?: AgentSkillSubscription[]
}

/**
 * Pre-defined Specialty Agents from Atom
 * These are the default agent templates that tenants can instantiate
 */
export const SPECIALTY_AGENTS: Omit<SpecialtyAgent, 'id' | 'status' | 'confidenceScore'>[] = [
    {
        name: 'Sales Agent',
        category: 'sales',
        description: 'Manages CRM pipelines, scores leads, and drafts outreach emails',
        capabilities: ['lead_scoring', 'email_drafting', 'pipeline_management', 'crm_sync'],
        moduleClass: 'SalesAgent'
    },
    {
        name: 'Marketing Agent',
        category: 'marketing',
        description: 'Automates campaigns, social posting, and analytics reports',
        capabilities: ['campaign_management', 'social_posting', 'analytics', 'content_generation'],
        moduleClass: 'MarketingAgent'
    },
    {
        name: 'Engineering Agent',
        category: 'engineering',
        description: 'Handles PR notifications, deployments, and incident response',
        capabilities: ['code_review', 'deployment', 'incident_response', 'jira_sync'],
        moduleClass: 'EngineeringAgent'
    },
    {
        name: 'Finance Agent',
        category: 'finance',
        description: 'Manages invoices, expense tracking, and financial reporting',
        capabilities: ['invoice_processing', 'expense_tracking', 'reporting', 'reconciliation'],
        moduleClass: 'FinanceAgent'
    },
    {
        name: 'HR Agent',
        category: 'hr',
        description: 'Handles employee onboarding, PTO tracking, and recruitment',
        capabilities: ['onboarding', 'pto_tracking', 'recruitment', 'performance_reviews'],
        moduleClass: 'HRAgent'
    },
    {
        name: 'Customer Success Agent',
        category: 'customer_success',
        description: 'Monitors customer health, handles support escalations, and renewal tracking',
        capabilities: ['health_scoring', 'support_escalation', 'renewal_tracking', 'feedback_collection'],
        moduleClass: 'CustomerSuccessAgent'
    },
    {
        name: 'Operations Agent',
        category: 'operations',
        description: 'Manages inventory, logistics, and process automation',
        capabilities: ['inventory_management', 'logistics', 'process_automation', 'vendor_management'],
        moduleClass: 'OperationsAgent'
    },
    {
        name: 'Data Analyst Agent',
        category: 'analytics',
        description: 'Analyzes data, generates insights, and creates visualizations',
        capabilities: ['data_analysis', 'insight_generation', 'visualization', 'trend_detection'],
        moduleClass: 'DataAnalystAgent'
    },
    {
        name: 'Shopify Swarm Orchestrator',
        category: 'ecommerce',
        description: 'Coordinates all Shopify lifecycle agents for end-to-end e-commerce operations',
        capabilities: ['inventory', 'orders', 'customers', 'marketing', 'analytics', 'lifecycle', 'fulfillment'],
        moduleClass: 'ShopifySwarmOrchestrator'
    },
    {
        name: 'Shopify Website Editor',
        category: 'ecommerce_design',
        description: 'Autonomously edits themes, updates banners, and modifies store layout via API',
        capabilities: ['theme_editing', 'visual_updates', 'layout_modification', 'asset_upload', 'liquid_template_editing'],
        moduleClass: 'ShopifyDesignAgent'
    },
    {
        name: 'Cloud Browser Agent',
        category: 'cloud_browser',
        description: 'Headless browser automation in the cloud (Playwright)',
        capabilities: [
            'browser_navigate', 'browser_click', 'browser_type', 'browser_screenshot',
            'browser_new_tab', 'browser_switch_tab', 'browser_click_coords', 'list_browser_tabs',
            'browser_save_session', 'browser_set_proxy', 'browser_monitor',
            'browser_wait_for_selector', 'browser_extract_content', 'browser_upload_file', 'browser_download_file',
            'web_search'
        ],
        moduleClass: 'CloudBrowserAgent'
    },
    {
        name: 'Custom Agent',
        category: 'custom',
        description: 'Flexible agent with user-defined capabilities',
        capabilities: ['general_reasoning', 'task_execution'],
        moduleClass: 'GenericAgent'
    },
    {
        name: 'Molty',
        category: 'orchestration_dynamic',
        description: 'Advanced AI assistant for high-level orchestration and dynamic skill creation. Based on the OpenClaw/Moltbot architecture.',
        capabilities: ['skill_creation', 'orchestration', 'formula_extraction', 'self_evolution'],
        moduleClass: 'MoltyAgent'
    }
];

export class SpecialtyAgentRegistry {
    private db: DatabaseService
    private skillRegistry: SkillRegistryService

    constructor(db: DatabaseService) {
        this.db = db
        this.skillRegistry = new SkillRegistryService()
    }

    /**
     * Get all available specialty agent templates
     */
    getTemplates(): typeof SPECIALTY_AGENTS {
        return SPECIALTY_AGENTS
    }

    /**
     * Create a specialty agent instance for a tenant
     */
    async createAgentFromTemplate(
        workspaceId: string,
        templateName: string,
        customName?: string
    ): Promise<SpecialtyAgent> {
        const template = SPECIALTY_AGENTS.find(
            a => a.name.toLowerCase() === templateName.toLowerCase() ||
                a.category.toLowerCase() === templateName.toLowerCase()
        )

        if (!template) {
            throw new Error(`Unknown specialty agent template: ${templateName}`)
        }

        const result = await this.db.query(`
            INSERT INTO agent_registry (
                name, workspace_id, category, 
                confidence_score, status,
                class_name, configuration,
                user_id, module_path
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $2, 'src/lib/ai/agents/specialty.ts')
            RETURNING *
        `, [
            customName || template.name,
            workspaceId,
            template.category,
            0.5, // Initial confidence
            'student', // Maps to status
            template.moduleClass,
            JSON.stringify({ capabilities: template.capabilities }) // Store capabilities in configuration JSON
        ])

        const agent = result.rows[0]

        return {
            id: agent.id,
            name: agent.name,
            category: agent.category,
            description: template.description,
            capabilities: template.capabilities,
            moduleClass: template.moduleClass,
            status: agent.maturity_level,
            confidenceScore: agent.confidence_score,
            skills: []
        }
    }

    /**
     * List all agents for a workspace
     */
    async listWorkspaceAgents(workspaceId: string): Promise<SpecialtyAgent[]> {
        const result = await this.db.query(`
            SELECT * FROM agent_registry WHERE workspace_id = $1
        `, [workspaceId])

        const agents: SpecialtyAgent[] = []

        for (const a of result.rows) {
            const skills = await this.skillRegistry.getAgentSkills(a.id)

            const config = typeof a.configuration === 'string' ? JSON.parse(a.configuration) : (a.configuration || {})
            const capabilities = config.capabilities || []

            agents.push({
                id: a.id,
                name: a.name,
                category: a.category,
                description: SPECIALTY_AGENTS.find(t => t.category === a.category)?.description || '',
                capabilities,
                moduleClass: a.class_name || 'GenericAgent',
                status: (a.status as any) || 'student',
                confidenceScore: a.confidence_score,
                skills
            })
        }

        return agents
    }
}
