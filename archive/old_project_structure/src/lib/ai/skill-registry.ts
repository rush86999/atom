import { DatabaseService, getDatabase } from '../database';

export interface SkillDefinition {
    id: string;
    workspaceId: string | null; // Null for global skills
    name: string;
    description: string;
    version: string;
    type: 'api' | 'function' | 'script' | 'docker' | 'container';
    inputSchema: any;
    outputSchema: any;
    config: any;
    isPublic: boolean;
    createdAt: Date;
    updatedAt: Date;
}

export interface AgentSkillSubscription {
    agentId: string;
    skillId: string;
    enabled: boolean;
    configOverrides: any;
    skill: SkillDefinition;
}

export class SkillRegistryService {
    private db: DatabaseService;

    constructor() {
        this.db = getDatabase();
    }

    /**
     * Create a new skill definition
     */
    async createSkill(skill: Omit<SkillDefinition, 'id' | 'createdAt' | 'updatedAt'>): Promise<SkillDefinition> {
        const result = await this.db.query(
            `INSERT INTO skills (
                workspace_id, name, description, version, type,
                input_schema, output_schema, config, is_public,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
            RETURNING *`,
            [
                skill.workspaceId,
                skill.name,
                skill.description,
                skill.version || '1.0.0',
                skill.type,
                JSON.stringify(skill.inputSchema),
                JSON.stringify(skill.outputSchema),
                JSON.stringify(skill.config),
                skill.isPublic
            ]
        );

        return this.mapRowToSkill(result.rows[0]);
    }

    /**
     * List all available skills for a tenant
     */
    async listAvailableSkills(workspaceId?: string): Promise<SkillDefinition[]> {
        let query = 'SELECT * FROM skills WHERE is_public = true';
        const params: any[] = [];

        if (workspaceId) {
            query += ' OR workspace_id = $1';
            params.push(workspaceId);
        }

        query += ' ORDER BY name ASC';

        const result = await this.db.query(query, params);
        return result.rows.map(this.mapRowToSkill);
    }

    /**
     * Assign a skill to an agent
     */
    async assignSkillToAgent(
        agentId: string,
        skillId: string,
        configOverrides?: any
    ): Promise<void> {
        await this.db.query(
            `INSERT INTO agent_skills (agent_id, skill_id, enabled, config_overrides, created_at)
             VALUES ($1, $2, true, $3, NOW())
             ON CONFLICT (agent_id, skill_id) 
             DO UPDATE SET enabled = true, config_overrides = $3`,
            [agentId, skillId, configOverrides ? JSON.stringify(configOverrides) : null]
        );
    }

    /**
     * Remove a skill from an agent
     */
    async removeSkillFromAgent(agentId: string, skillId: string): Promise<void> {
        await this.db.query(
            `DELETE FROM agent_skills WHERE agent_id = $1 AND skill_id = $2`,
            [agentId, skillId]
        );
    }

    /**
     * Get all skills assigned to a specific agent
     */
    async getAgentSkills(agentId: string): Promise<AgentSkillSubscription[]> {
        const result = await this.db.query(
            `SELECT as_join.*, s.*
             FROM agent_skills as_join
             JOIN skills s ON as_join.skill_id = s.id
             WHERE as_join.agent_id = $1 AND as_join.enabled = true`,
            [agentId]
        );

        return result.rows.map(row => ({
            agentId: row.agent_id,
            skillId: row.skill_id,
            enabled: row.enabled,
            configOverrides: row.config_overrides,
            skill: this.mapRowToSkill(row)
        }));
    }

    /**
     * Get a specific skill by ID
     */
    async getSkill(skillId: string): Promise<SkillDefinition | null> {
        const result = await this.db.query(
            `SELECT * FROM skills WHERE id = $1`,
            [skillId]
        );

        if (result.rows.length === 0) return null;
        return this.mapRowToSkill(result.rows[0]);
    }

    private mapRowToSkill(row: any): SkillDefinition {
        return {
            id: row.id,
            workspaceId: row.workspace_id,
            name: row.name,
            description: row.description,
            version: row.version,
            type: row.type,
            inputSchema: typeof row.input_schema === 'string' ? JSON.parse(row.input_schema) : row.input_schema,
            outputSchema: typeof row.output_schema === 'string' ? JSON.parse(row.output_schema) : row.output_schema,
            config: typeof row.config === 'string' ? JSON.parse(row.config) : row.config,
            isPublic: row.is_public,
            createdAt: row.created_at,
            updatedAt: row.updated_at
        };
    }
}
