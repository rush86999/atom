import { DatabaseService } from '../database'

export interface AgentExperience {
    agent_id: string
    task_type: string
    input_summary: string
    outcome: string
    learnings: string
    agent_role: string
    specialty?: string
    artifacts?: string[]
}

export class WorldModelService {
    private db: DatabaseService

    constructor(db: DatabaseService) {
        this.db = db
    }

    async recordExperience(tenantId: string, experience: AgentExperience): Promise<void> {
        const textRepresentation = `
Task: ${experience.task_type}
Input: ${experience.input_summary}
Outcome: ${experience.outcome}
Learnings: ${experience.learnings}
        `.trim()

        const metadata = {
            agent_id: experience.agent_id,
            task_type: experience.task_type,
            outcome: experience.outcome,
            agent_role: experience.agent_role,
            specialty: experience.specialty,
            artifacts: experience.artifacts,
            type: 'experience'
        }

        await this.db.storeMemory(
            tenantId,
            'experience',
            textRepresentation,
            metadata
        )
    }

    async recordFormulaUsage(
        tenantId: string,
        data: {
            agent_id: string
            agent_role: string
            formula_id: string
            formula_name: string
            task_description: string
            inputs: any
            result: any
            success: boolean
            learnings?: string
        }
    ): Promise<void> {
        const textRepresentation = `
Task: formula_application
Input: Applied '${data.formula_name}' for ${data.task_description}
Outcome: ${data.success ? 'Success' : 'Failure'}
Learnings: ${data.learnings || `Formula ${data.formula_name} used with inputs ${JSON.stringify(data.inputs)}`}
        `.trim()

        const metadata = {
            agent_id: data.agent_id,
            task_type: 'formula_application',
            outcome: data.success ? 'Success' : 'Failure',
            agent_role: data.agent_role,
            specialty: 'formulas',
            type: 'experience',
            formula_id: data.formula_id,
            formula_name: data.formula_name,
            formula_inputs: JSON.stringify(data.inputs),
            formula_result: String(data.result)
        }

        await this.db.storeMemory(
            tenantId,
            'experience',
            textRepresentation,
            metadata
        )
    }

    async recallExperiences(
        tenantId: string,
        agentRole: string,
        taskDescription: string,
        limit: number = 5
    ): Promise<{
        experiences: any[]
        knowledge: any[]
        formulas: any[]
    }> {
        // Search using vector similarity on the 'content' column
        const results = await this.db.queryMemories(
            tenantId,
            taskDescription,
            limit * 3,
            'experience'
        )

        const agentCategory = agentRole.toLowerCase()

        // Filter for relevance to the agent's role
        const experiences = results.filter(mem => {
            const meta = mem.metadata as any
            const memoryRole = (meta.agent_role || '').toLowerCase()
            return memoryRole === agentCategory || memoryRole === 'general'
        }).slice(0, limit).map(mem => ({
            id: mem.id,
            content: mem.content,
            metadata: mem.metadata,
            created_at: mem.created_at
        }))

        // Search general knowledge
        const knowledge = await this.db.queryMemories(
            tenantId,
            taskDescription,
            limit,
            'document'
        )

        // Search formulas (stored as 'formula' type)
        const formulas = await this.db.queryMemories(
            tenantId,
            taskDescription,
            limit,
            'formula'
        )

        return {
            experiences,
            knowledge: knowledge.map(k => ({
                id: k.id,
                content: k.content,
                type: 'knowledge'
            })),
            formulas: formulas.map(f => ({
                id: f.id,
                name: (f.metadata as any)?.formula_name || 'Unknown',
                expression: (f.metadata as any)?.expression,
                domain: (f.metadata as any)?.domain,
                type: 'formula'
            }))
        }
    }

    async recordFeedback(
        tenantId: string,
        data: {
            agent_id: string
            user_id: string
            rating: number
            comment: string
            original_output?: string
            user_correction?: string
            task_type?: string
            agent_role?: string
        }
    ): Promise<void> {
        const textRepresentation = `
Feedback Rating: ${data.rating}/5
Comment: ${data.comment}
Original Output: ${data.original_output || 'N/A'}
User Correction: ${data.user_correction || 'N/A'}
        `.trim()

        const metadata = {
            agent_id: data.agent_id,
            user_id: data.user_id,
            rating: data.rating,
            task_type: data.task_type || 'feedback',
            agent_role: data.agent_role || 'general',
            type: 'feedback'
        }

        await this.db.storeMemory(
            tenantId,
            'feedback',
            textRepresentation,
            metadata
        )
    }
}
