import { SkillRegistryService, SkillDefinition } from './skill-registry';
import { v4 as uuidv4 } from 'uuid';

/**
 * Dynamic Skill Tools
 * 
 * Provides tools for agents to create and register new skills at runtime.
 */

export class DynamicSkillBuilder {
    private skillRegistry: SkillRegistryService;

    constructor() {
        this.skillRegistry = new SkillRegistryService();
    }

    /**
     * Synthesize and register a new script skill
     */
    async registerScriptSkill(
        workspaceId: string,
        agentId: string,
        params: {
            name: string;
            description: string;
            code: string;
            inputSchema: any;
            outputSchema: any;
        }
    ): Promise<SkillDefinition> {
        const skill = await this.skillRegistry.createSkill({
            workspaceId,
            name: params.name,
            description: params.description,
            version: '1.0.0',
            type: 'script',
            inputSchema: params.inputSchema,
            outputSchema: params.outputSchema,
            config: { code: params.code },
            isPublic: false
        });

        // Automatically assign to the agent that created it
        await this.skillRegistry.assignSkillToAgent(agentId, skill.id);

        return skill;
    }

    /**
     * Register a new API skill
     */
    async registerApiSkill(
        workspaceId: string,
        agentId: string,
        params: {
            name: string;
            description: string;
            url: string;
            method: 'GET' | 'POST' | 'PUT' | 'DELETE';
            headers?: Record<string, string>;
            inputSchema: any;
            outputSchema: any;
        }
    ): Promise<SkillDefinition> {
        const skill = await this.skillRegistry.createSkill({
            workspaceId,
            name: params.name,
            description: params.description,
            version: '1.0.0',
            type: 'api',
            inputSchema: params.inputSchema,
            outputSchema: params.outputSchema,
            config: {
                url: params.url,
                method: params.method,
                headers: params.headers || {}
            },
            isPublic: false
        });

        // Automatically assign to the agent that created it
        await this.skillRegistry.assignSkillToAgent(agentId, skill.id);

        return skill;
    }

    /**
     * Register a new containerized skill (Fly.io Machine)
     */
    async registerContainerSkill(
        workspaceId: string,
        agentId: string,
        params: {
            name: string;
            description: string;
            image: string;
            env?: Record<string, string>;
            inputSchema: any;
            outputSchema: any;
        }
    ): Promise<SkillDefinition> {
        const skill = await this.skillRegistry.createSkill({
            workspaceId,
            name: params.name,
            description: params.description,
            version: '1.0.0',
            type: 'container',
            inputSchema: params.inputSchema,
            outputSchema: params.outputSchema,
            config: {
                image: params.image,
                env: params.env || {}
            },
            isPublic: false
        });

        // Automatically assign to the agent that created it
        await this.skillRegistry.assignSkillToAgent(agentId, skill.id);

        return skill;
    }

    /**
     * Register a new local Docker skill (Desktop/Tauri only)
     */
    async registerDockerSkill(
        workspaceId: string,
        agentId: string,
        params: {
            name: string;
            description: string;
            image: string;
            command?: string;
            inputSchema: any;
            outputSchema: any;
        }
    ): Promise<SkillDefinition> {
        const skill = await this.skillRegistry.createSkill({
            workspaceId,
            name: params.name,
            description: params.description,
            version: '1.0.0',
            type: 'docker',
            inputSchema: params.inputSchema,
            outputSchema: params.outputSchema,
            config: {
                image: params.image,
                command: params.command || ''
            },
            isPublic: false
        });

        // Automatically assign to the agent that created it
        await this.skillRegistry.assignSkillToAgent(agentId, skill.id);

        return skill;
    }
}

// Singleton
let dynamicSkillBuilder: DynamicSkillBuilder | null = null;
export function getDynamicSkillBuilder(): DynamicSkillBuilder {
    if (!dynamicSkillBuilder) {
        dynamicSkillBuilder = new DynamicSkillBuilder();
    }
    return dynamicSkillBuilder;
}
