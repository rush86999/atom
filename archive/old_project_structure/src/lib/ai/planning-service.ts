import { DatabaseService, getDatabase } from '../database';
import { WorldModelService } from './world-model';

export interface AgentTask {
    id: string;
    list_id: string;
    parent_task_id: string | null;
    description: string;
    status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'blocked';
    priority: 'high' | 'medium' | 'low';
    dependencies: string[];
    metadata: Record<string, any>;
    order_index: number;
    created_at: Date;
    updated_at: Date;
}

export interface AgentTaskList {
    id: string;
    agent_id: string;
    tenant_id: string;
    title: string;
    status: 'active' | 'completed' | 'archived';
    tasks: AgentTask[];
    created_at: Date;
    updated_at: Date;
}

export interface AgentPlan {
    id: string;
    agent_id: string;
    title: string;
    content: string;
    status: 'draft' | 'review' | 'approved' | 'archived';
    version: number;
    created_at: Date;
    updated_at: Date;
}

export interface AgentComment {
    id: string;
    resource_id: string;
    resource_type: 'plan' | 'task_list' | 'trace' | 'step';
    user_id: string;
    content: string;
    resolved: boolean;
    resolution_summary?: string;
    created_at: Date;
}

export class PlanningService {
    private db: DatabaseService;
    private worldModel: WorldModelService;

    constructor(db: DatabaseService) {
        this.db = db;
        this.worldModel = new WorldModelService(db);
    }

    /**
     * Get active approved plan for an agent
     */
    async getActivePlan(tenantId: string, agentId: string): Promise<AgentPlan | null> {
        const res = await this.db.query(
            `SELECT * FROM agent_plans WHERE tenant_id = $1 AND agent_id = $2 AND status = 'approved' ORDER BY created_at DESC LIMIT 1`,
            [tenantId, agentId]
        );
        return res.rows[0] || null;
    }

    /**
     * Create or update a plan
     */
    async savePlan(
        tenantId: string,
        agentId: string,
        title: string,
        content: string,
        userId: string,
        status: 'draft' | 'review' | 'approved' = 'draft'
    ): Promise<AgentPlan> {
        const res = await this.db.query(`
            INSERT INTO agent_plans (tenant_id, agent_id, title, content, author_id, status, version)
            VALUES ($1, $2, $3, $4, $5, $6, 1)
            RETURNING *
        `, [tenantId, agentId, title, content, userId, status]);

        return res.rows[0];
    }

    /**
     * Add a comment to a plan or task list
     */
    async addComment(
        tenantId: string,
        resourceId: string,
        resourceType: 'plan' | 'task_list' | 'trace' | 'step',
        userId: string,
        content: string
    ): Promise<AgentComment> {
        const res = await this.db.query(`
            INSERT INTO agent_comments (tenant_id, resource_id, resource_type, user_id, content)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        `, [tenantId, resourceId, resourceType, userId, content]);

        return res.rows[0];
    }

    /**
     * Resolve a comment and record it as a learning experience
     */
    async resolveComment(
        tenantId: string,
        commentId: string,
        resolutionSummary: string,
        agentId: string
    ): Promise<void> {
        // 1. Update comment status
        await this.db.query(`
            UPDATE agent_comments 
            SET resolved = true, resolution_summary = $1, updated_at = NOW()
            WHERE id = $2
        `, [resolutionSummary, commentId]);

        // 2. Fetch original comment for context
        const commentRes = await this.db.query(`SELECT content FROM agent_comments WHERE id = $1`, [commentId]);
        const originalComment = commentRes.rows[0]?.content || 'Unknown comment';

        // 3. Record learning experience in World Model
        await this.worldModel.recordExperience(tenantId, {
            agent_id: agentId,
            task_type: 'collaborative_planning',
            input_summary: `User Feedback: "${originalComment}"`,
            outcome: 'Plan/Approach Modified',
            learnings: `Incorporated feedback: ${resolutionSummary}`,
            agent_role: 'system', // or fetch agent role
            specialty: 'planning'
        });

        // console.log(`[PlanningService] Resolved comment ${commentId} and recorded learning.`);
    }

    /**
     * Get comments for a resource
     */
    async getComments(tenantId: string, resourceId: string): Promise<AgentComment[]> {
        const res = await this.db.query(
            `SELECT * FROM agent_comments WHERE tenant_id = $1 AND resource_id = $2 ORDER BY created_at ASC`,
            [tenantId, resourceId]
        );
        return res.rows;
    }

    /**
     * Create a new persistent task list for an agent
     */
    async createTaskList(agentId: string, tenantId: string, title: string): Promise<AgentTaskList> {
        // Try to handle both title and name columns for compatibility
        const res = await this.db.query(`
            INSERT INTO agent_task_lists (agent_id, tenant_id, title, name, status)
            VALUES ($1, $2, $3, $4, 'active')
            RETURNING *
        `, [agentId, tenantId, title, title]);

        return {
            ...res.rows[0],
            tasks: []
        };
    }

    /**
     * Get active task list with all tasks
     */
    async getActiveTaskList(agentId: string, tenantId: string): Promise<AgentTaskList | null> {
        const listRes = await this.db.query(`
            SELECT * FROM agent_task_lists 
            WHERE agent_id = $1 AND tenant_id = $2 AND status = 'active' 
            ORDER BY created_at DESC LIMIT 1
        `, [agentId, tenantId]);

        if (listRes.rows.length === 0) return null;

        const list = listRes.rows[0];
        const tasksRes = await this.db.query(`
            SELECT * FROM agent_tasks 
            WHERE list_id = $1 
            ORDER BY order_index ASC
        `, [list.id]);

        return {
            ...list,
            tasks: tasksRes.rows
        };
    }

    /**
     * Add a task to an existing list
     */
    async addTask(
        listId: string,
        description: string,
        priority: 'high' | 'medium' | 'low' = 'medium',
        parentId: string | null = null,
        metadata: any = {}
    ): Promise<AgentTask> {
        // Get current max order index
        const orderRes = await this.db.query(`
            SELECT MAX(order_index) as max_order FROM agent_tasks WHERE list_id = $1
        `, [listId]);
        const nextOrder = (orderRes.rows[0].max_order || 0) + 1;

        const res = await this.db.query(`
            INSERT INTO agent_tasks (
                list_id, description, status, priority, parent_task_id, 
                metadata, order_index
            )
            VALUES ($1, $2, 'pending', $3, $4, $5, $6)
            RETURNING *
        `, [listId, description, priority, parentId, metadata, nextOrder]);

        return res.rows[0];
    }

    /**
     * Update task status
     */
    async updateTaskStatus(
        taskId: string,
        status: AgentTask['status'],
        metadataUpdates?: any
    ): Promise<AgentTask> {
        let query = `UPDATE agent_tasks SET status = $1, updated_at = NOW()`;
        const params = [status, taskId];
        let paramIndex = 3;

        if (metadataUpdates) {
            query += `, metadata = metadata || $${paramIndex - 1}`; // Simple JSONB merge
            // params.push(metadataUpdates); -> Wait, correct param index handling
            // Correct approach:
            query = `
                UPDATE agent_tasks 
                SET status = $1, 
                    metadata = CASE WHEN $2::jsonb IS NOT NULL THEN metadata || $2::jsonb ELSE metadata END,
                    updated_at = NOW()
                WHERE id = $3
                RETURNING *
            `;
            return (await this.db.query(query, [status, JSON.stringify(metadataUpdates || null), taskId])).rows[0];
        } else {
            query += ` WHERE id = $2 RETURNING *`;
            return (await this.db.query(query, [status, taskId])).rows[0];
        }
    }
}

let planningService: PlanningService | null = null;

export function getPlanningService(): PlanningService {
    if (!planningService) {
        const db = getDatabase();
        planningService = new PlanningService(db);
    }
    return planningService;
}
