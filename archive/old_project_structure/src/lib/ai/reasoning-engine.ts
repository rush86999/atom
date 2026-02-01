import { DatabaseService } from '../database'
import { v4 as uuidv4 } from 'uuid'
import { LLMRouter } from './llm-router'
import { WorldModelService } from './world-model'

export interface Intervention {
    id: string
    tenant_id: string
    type: 'URGENT' | 'OPPORTUNITY' | 'AUTOMATION'
    title: string
    description: string
    suggested_action: string
    action_payload: any
    status: 'PENDING' | 'DISMISSED' | 'ACTED'
    created_at: Date
}

export class ReasoningEngine {
    private db: DatabaseService
    private llm: LLMRouter
    private worldModel: WorldModelService

    constructor(db: DatabaseService) {
        this.db = db
        this.llm = new LLMRouter(db)
        this.worldModel = new WorldModelService(db)
    }

    async generateInterventions(tenantId: string): Promise<Intervention[]> {
        try {
            // 1. Collect Context Data from Hybrid Memory (Direct Service Call)
            // Using "General Context" as a search query to get broad recent state
            const hybridContext = await this.worldModel.recallExperiences(
                tenantId,
                'system_reasoner', // Role
                'recent context analysis', // Task Description
                20 // Limit
            )

            const context = {
                hybridContext,
                timestamp: new Date().toISOString()
            }

            // 2. Query LLM for Proactive Insights
            const prompt = `
            You are the "Atom Proactive Intelligence" brain for a SaaS tenant.
            Your job is to analyze recent activity and state to suggest "Interventions".
            
            Context:
            ${JSON.stringify(context, null, 2)}

            Identify 3 key interventions:
            1. URGENT: Something critical that needs attention (e.g. churn risk, system failures).
            2. OPPORTUNITY: A way to provide more value or upsell (e.g. heavy usage, missing integrations).
            3. AUTOMATION: A repetitive task that could be automated.

            Return a valid JSON array of objects with this schema:
            [
              {
                "type": "URGENT" | "OPPORTUNITY" | "AUTOMATION",
                "title": "Short title",
                "description": "Clear explanation",
                "suggested_action": "internal_command_slug",
                "action_payload": {}
              }
            ]
            `

            const response = await this.llm.call(tenantId, {
                model: 'gpt-4o-mini',
                type: 'analysis',
                messages: [
                    { role: 'system', content: 'You are a proactive SaaS intelligence engine. Always return valid JSON.' },
                    { role: 'user', content: prompt }
                ]
            })

            const suggestedInterventions = JSON.parse(response.content.replace(/```json|```/g, ''))

            return suggestedInterventions.map((si: any) => ({
                id: uuidv4(),
                tenant_id: tenantId,
                ...si,
                status: 'PENDING',
                created_at: new Date()
            }))

        } catch (error) {
            console.error('Error in ReasoningEngine:', error)
            return [] // Fallback to empty if LLM fails
        }
    }
}
