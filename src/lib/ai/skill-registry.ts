import { DatabaseService, getDatabase } from '../database';

export interface SkillDefinition {
    id: string;
    tenantId: string | null; // Null for global skills
    name: string;
    description: string;
    version: string;
    type: 'api' | 'function' | 'script' | 'docker' | 'container' | 'terminal' | 'browser' | 'openclaw';
    inputSchema: any;
    outputSchema: any;
    config: any;
    isPublic: boolean;
    createdAt: Date;
    updatedAt: Date;
    // OpenClaw-specific fields
    safetyLevel?: 'SAFE' | 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK' | 'BLOCKED' | 'UNKNOWN';
    openclawMetadata?: {
        parameters?: Record<string, string>;
        execution?: {
            image?: string;
            command?: string;
            cpu_count?: number;
            memory_mb?: number;
        };
    };
}

/**
 * OpenClaw skill definition with execution metadata
 */
export interface OpenClawSkillDefinition extends Omit<SkillDefinition, 'type'> {
    type: 'openclaw';
    safetyLevel: SkillDefinition['safetyLevel'];
    openclawMetadata: NonNullable<SkillDefinition['openclawMetadata']>;
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
                tenant_id, name, description, version, type,
                input_schema, output_schema, config, is_public,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
            RETURNING *`,
            [
                skill.tenantId,
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
    async listAvailableSkills(tenantId?: string): Promise<SkillDefinition[]> {
        let query = 'SELECT * FROM skills WHERE is_public = true';
        const params: any[] = [];

        if (tenantId) {
            query += ' OR tenant_id = $1';
            params.push(tenantId);
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
     * Extended to include OpenClaw skills from backend API
     */
    async getAgentSkills(agentId: string, tenantId?: string): Promise<AgentSkillSubscription[]> {
        // Get database skills first
        const result = await this.db.query(
            `SELECT as_join.*, s.*
             FROM agent_skills as_join
             JOIN skills s ON as_join.skill_id = s.id
             WHERE as_join.agent_id = $1 AND as_join.enabled = true`,
            [agentId]
        );

        const skills = result.rows.map(row => ({
            agentId: row.agent_id,
            skillId: row.skill_id,
            enabled: row.enabled,
            configOverrides: row.config_overrides,
            skill: this.mapRowToSkill(row)
        }));

        // If tenantId provided, fetch OpenClaw skills from backend
        if (tenantId) {
            try {
                const openclawSkills = await this.getOpenClawSkills(tenantId);
                // Merge OpenClaw skills (they're not in agent_skills table yet)
                for (const ocSkill of openclawSkills) {
                    // Skip if already in list
                    if (skills.some(s => s.skillId === ocSkill.id)) continue;

                    skills.push({
                        agentId,
                        skillId: ocSkill.id,
                        enabled: true, // OpenClaw skills are tenant-scoped, always available
                        configOverrides: null,
                        skill: ocSkill
                    });
                }
            } catch (error) {
                console.warn('[SkillRegistry] Failed to fetch OpenClaw skills:', error);
                // Don't fail entire operation if OpenClaw fetch fails
            }
        }

        return skills;
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
            tenantId: row.tenant_id,
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

    /**
     * Get a specific OpenClaw skill by ID from backend API
     */
    async getOpenClawSkill(skillId: string, tenantId: string): Promise<SkillDefinition | null> {
        try {
            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.PYTHON_BACKEND_URL || 'http://127.0.0.1:8000';
            const response = await fetch(`${backendUrl}/api/skills/openclaw/skills?tenant_id=${tenantId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Tenant-Id': tenantId
                }
            });

            if (!response.ok) {
                console.warn(`[SkillRegistry] Failed to fetch OpenClaw skills: ${response.status}`);
                return null;
            }

            const data = await response.json();
            const skills = data.skills || data || [];

            // Find the specific skill by ID
            const skill = skills.find((s: any) => s.id === skillId || s.skill_id === skillId);
            if (!skill) return null;

            return this.mapOpenClawSkillToDefinition(skill);
        } catch (error) {
            console.error('[SkillRegistry] Error fetching OpenClaw skill:', error);
            return null;
        }
    }

    /**
     * Get all OpenClaw skills for a tenant from backend API
     */
    async getOpenClawSkills(tenantId: string): Promise<SkillDefinition[]> {
        try {
            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.PYTHON_BACKEND_URL || 'http://127.0.0.1:8000';
            const response = await fetch(`${backendUrl}/api/skills/openclaw/skills?tenant_id=${tenantId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Tenant-Id': tenantId
                }
            });

            if (!response.ok) {
                console.warn(`[SkillRegistry] Failed to fetch OpenClaw skills: ${response.status}`);
                return [];
            }

            const data = await response.json();
            const skills = data.skills || data || [];

            return skills.map((s: any) => this.mapOpenClawSkillToDefinition(s));
        } catch (error) {
            console.error('[SkillRegistry] Error fetching OpenClaw skills:', error);
            return [];
        }
    }

    /**
     * Map OpenClaw API response to SkillDefinition
     */
    private mapOpenClawSkillToDefinition(apiSkill: any): SkillDefinition {
        // Extract parameters from openclaw_metadata for inputSchema
        const openclawMetadata = apiSkill.openclaw_metadata || {};
        const parameters = openclawMetadata.parameters || {};

        return {
            id: apiSkill.id || apiSkill.skill_id,
            tenantId: apiSkill.tenant_id,
            name: apiSkill.name,
            description: apiSkill.description,
            version: apiSkill.version || '1.0.0',
            type: 'openclaw',
            inputSchema: Object.keys(parameters).length > 0 ? parameters : { type: 'object' },
            outputSchema: openclawMetadata.output_schema || { type: 'object' },
            config: {
                ...openclawMetadata.execution,
                safetyLevel: apiSkill.safety_level,
                openclawSourceUrl: apiSkill.openclaw_source_url
            },
            isPublic: apiSkill.is_public || false,
            safetyLevel: apiSkill.safety_level || 'UNKNOWN',
            openclawMetadata: {
                parameters,
                execution: openclawMetadata.execution || {}
            },
            createdAt: new Date(apiSkill.created_at || Date.now()),
            updatedAt: new Date(apiSkill.updated_at || Date.now())
        };
    }
}
