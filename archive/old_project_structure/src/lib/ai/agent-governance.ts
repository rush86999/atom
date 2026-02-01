import { DatabaseService } from '../database'

export type MaturityLevel = 'student' | 'intern' | 'supervised' | 'autonomous'

export const ACTION_COMPLEXITY: Record<string, number> = {
    // Low risk
    "search": 1, "read": 1, "list": 1, "get": 1, "fetch": 1, "summarize": 1,
    // Medium-low
    "analyze": 2, "suggest": 2, "draft": 2, "generate": 2, "recommend": 2,
    // Medium
    "create": 3, "update": 3, "send_email": 3, "post_message": 3, "schedule": 3, "ingest": 3,
    // High
    "delete": 4, "execute": 4, "deploy": 4, "transfer": 4, "payment": 4, "approve": 4, "register": 4,
}

export const MATURITY_REQUIREMENTS: Record<number, MaturityLevel> = {
    1: 'student',
    2: 'intern',
    3: 'supervised',
    4: 'autonomous',
}

export class AgentGovernanceService {
    private db: DatabaseService

    constructor(db: DatabaseService) {
        this.db = db
    }

    async canPerformAction(
        tenantId: string,
        agentId: string,
        actionType: string
    ): Promise<{
        allowed: boolean
        reason: string
        requires_approval: boolean
        maturity_level: MaturityLevel
        complexity: number
    }> {
        // In a real app, we'd fetch the agent from DB. 
        // Assuming DatabaseService has getAgentById or generic query.
        // For now, we'll query the agents table directly via SQL.
        const res = await this.db.query(
            'SELECT * FROM agent_registry WHERE id = $1 AND tenant_id = $2',
            [agentId, tenantId]
        )

        if (res.rows.length === 0) {
            return {
                allowed: false,
                reason: 'Agent not found',
                requires_approval: true,
                maturity_level: 'student', // Default fallback
                complexity: 0
            }
        }

        const agent = res.rows[0]
        const agentMaturity: MaturityLevel = agent.maturity_level || 'student'

        // Determine complexity
        let complexity = 2 // Default medium-low
        for (const [key, level] of Object.entries(ACTION_COMPLEXITY)) {
            if (actionType.toLowerCase().includes(key)) {
                complexity = level
                break
            }
        }

        const requiredMaturity = MATURITY_REQUIREMENTS[complexity]

        const maturityOrder: MaturityLevel[] = ['student', 'intern', 'supervised', 'autonomous']
        const agentIndex = maturityOrder.indexOf(agentMaturity)
        const requiredIndex = maturityOrder.indexOf(requiredMaturity)

        const isAllowed = agentIndex >= requiredIndex
        // Supervised agents might need approval for high complexity actions
        const requiresApproval = !isAllowed || (agentMaturity === 'supervised' && complexity >= 3)

        return {
            allowed: isAllowed,
            reason: isAllowed
                ? `Agent ${agent.name} (${agentMaturity}) authorized for complexity ${complexity}`
                : `Agent ${agent.name} (${agentMaturity}) lacks maturity for ${actionType} (Req: ${requiredMaturity})`,
            requires_approval: requiresApproval,
            maturity_level: agentMaturity,
            complexity
        }
    }

    async updateAgentScore(tenantId: string, agentId: string, delta: number): Promise<void> {
        // Enforce bounds 0.0 to 1.0
        await this.db.query(`
            UPDATE agent_registry 
            SET confidence_score = GREATEST(0.0, LEAST(1.0, confidence_score + $1)),
                updated_at = NOW()
            WHERE id = $2 AND tenant_id = $3
        `, [delta, agentId, tenantId])
    }

    async promoteAgent(tenantId: string, agentId: string, newLevel: MaturityLevel): Promise<void> {
        await this.db.query(`
            UPDATE agent_registry 
            SET maturity_level = $1, updated_at = NOW()
            WHERE id = $2 AND tenant_id = $3
        `, [newLevel, agentId, tenantId])
    }

    // ==================== FEEDBACK SYSTEM (Synced from Atom) ====================

    async submitFeedback(
        tenantId: string,
        data: {
            agentId: string
            userId: string
            originalOutput?: string
            userCorrection?: string
            inputContext?: string
            executionId?: string
            traceStepId?: string
            rating?: number
            comment?: string
        }
    ): Promise<{ feedbackId: string; status: string; reasoning: string }> {
        // Store feedback record in "Hot" storage (Postgres)
        const feedbackId = `fb_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`

        await this.db.query(`
            INSERT INTO agent_feedback (
                id, tenant_id, agent_id, user_id, 
                original_output, user_correction, input_context, 
                execution_id, trace_step_id, rating, comment,
                status, created_at, processed_for_learning
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'pending', NOW(), false)
        `, [
            feedbackId,
            tenantId,
            data.agentId,
            data.userId,
            data.originalOutput || null,
            data.userCorrection || null,
            data.inputContext || null,
            data.executionId || null,
            data.traceStepId || null,
            data.rating || null,
            data.comment || data.userCorrection || null,
        ])

        // Trigger adjudication (Hot adjustments to agent score)
        const result = await this.adjudicateFeedback(tenantId, feedbackId, data.userId, data.agentId)

        return {
            feedbackId,
            status: result.status,
            reasoning: result.reasoning
        }
    }

    private async adjudicateFeedback(
        tenantId: string,
        feedbackId: string,
        userId: string,
        agentId: string
    ): Promise<{ status: string; reasoning: string }> {
        // Get user details
        const userResult = await this.db.query(
            'SELECT role, specialty FROM users WHERE id = $1 AND tenant_id = $2',
            [userId, tenantId]
        )
        const user = userResult.rows[0]

        // Get agent category
        const agentResult = await this.db.query(
            'SELECT category FROM agent_registry WHERE id = $1 AND tenant_id = $2',
            [agentId, tenantId]
        )
        const agent = agentResult.rows[0]

        // Check if trusted reviewer
        const isAdmin = user?.role === 'super_admin' || user?.role === 'workspace_admin'
        const isSpecialtyMatch = user?.specialty?.toLowerCase() === agent?.category?.toLowerCase()
        const isTrustedReviewer = isAdmin || isSpecialtyMatch

        let status: string
        let reasoning: string

        if (isTrustedReviewer) {
            status = 'accepted'
            reasoning = `Trusted reviewer (Role: ${user?.role}, Specialty: ${user?.specialty}) provided correction.`

            // High impact on confidence score
            await this.updateAgentScore(tenantId, agentId, -0.1)
            await this.checkAndUpdateMaturity(tenantId, agentId)
        } else {
            status = 'pending_review'
            reasoning = 'Correction queued for specialty review.'

            // Low impact
            await this.updateAgentScore(tenantId, agentId, -0.02)
        }

        // Update feedback record
        await this.db.query(`
            UPDATE agent_feedback 
            SET status = $1, ai_reasoning = $2, adjudicated_at = NOW()
            WHERE id = $3 AND tenant_id = $4
        `, [status, reasoning, feedbackId, tenantId])

        return { status, reasoning }
    }

    private async checkAndUpdateMaturity(tenantId: string, agentId: string): Promise<void> {
        const result = await this.db.query(
            'SELECT confidence_score, maturity_level FROM agent_registry WHERE id = $1 AND tenant_id = $2',
            [agentId, tenantId]
        )
        const agent = result.rows[0]
        if (!agent) return

        const score = agent.confidence_score || 0.5
        let newLevel: MaturityLevel

        if (score >= 0.9) newLevel = 'autonomous'
        else if (score >= 0.7) newLevel = 'supervised'
        else if (score >= 0.5) newLevel = 'intern'
        else newLevel = 'student'

        if (newLevel !== agent.maturity_level) {
            await this.promoteAgent(tenantId, agentId, newLevel)
            console.log(`Agent ${agentId} maturity changed: ${agent.maturity_level} -> ${newLevel} (Score: ${score.toFixed(2)})`)
        }
    }

    // ==================== FORMULA LEARNING (Synced from Atom) ====================

    /**
     * Record formula usage outcome and adjust agent confidence.
     * Low-impact learning: +0.01 for success, -0.02 for failure.
     */
    async recordFormulaLearning(
        tenantId: string,
        agentId: string,
        formulaId: string,
        success: boolean
    ): Promise<void> {
        const delta = success ? 0.01 : -0.02 // Low-impact learning
        await this.updateAgentScore(tenantId, agentId, delta)
        await this.checkAndUpdateMaturity(tenantId, agentId)

        console.log(`[Governance] Formula learning for agent ${agentId}: ${success ? 'success' : 'failure'} (delta: ${delta})`)
    }
}
