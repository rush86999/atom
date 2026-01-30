import { DatabaseService, getDatabase } from '../database';
import { SkillDefinition } from './skill-registry';
import { parseArgsStringToArgv } from 'string-argv';

export interface SkillExecutionResult {
    executionId: string;
    status: 'completed' | 'failed';
    result: any;
    error?: string;
    durationMs: number;
}

export class SkillExecutorService {
    private db: DatabaseService;

    constructor() {
        this.db = getDatabase();
    }

    /**
     * Execute a skill with given parameters
     */
    async executeSkill(
        skill: SkillDefinition,
        params: any,
        agentId: string,
        workspaceId: string | null,
        configOverrides?: any
    ): Promise<SkillExecutionResult> {
        const startTime = Date.now();

        // 1. Create execution record
        const execRecord = await this.db.query(
            `INSERT INTO skill_executions (agent_id, skill_id, workspace_id, status, input_params, created_at)
             VALUES ($1, $2, $3, 'running', $4, NOW())
             RETURNING id`,
            [agentId, skill.id, workspaceId, JSON.stringify(params)]
        );
        const executionId = execRecord.rows[0].id;

        try {
            let result: any;

            // 2. Route execution based on type
            switch (skill.type) {
                case 'api':
                    result = await this.executeApiSkill(skill, params, configOverrides);
                    break;
                case 'script':
                    result = await this.executeScriptSkill(skill, params, configOverrides);
                    break;
                case 'docker':
                    result = await this.executeDockerSkill(skill, params, configOverrides);
                    break;
                default:
                    throw new Error(`Unsupported skill type: ${skill.type}`);
            }

            // 3. Update execution record on success
            const duration = Date.now() - startTime;
            await this.db.query(
                `UPDATE skill_executions
                 SET status = 'completed', output_result = $1, execution_time_ms = $2
                 WHERE id = $3`,
                [JSON.stringify(result), duration, executionId]
            );

            return {
                executionId,
                status: 'completed',
                result,
                durationMs: duration
            };

        } catch (error: any) {
            // 4. Update execution record on failure
            const duration = Date.now() - startTime;
            await this.db.query(
                `UPDATE skill_executions 
                 SET status = 'failed', error_message = $1, execution_time_ms = $2
                 WHERE id = $3`,
                [error.message, duration, executionId]
            );

            return {
                executionId,
                status: 'failed',
                result: null,
                error: error.message,
                durationMs: duration
            };
        }
    }

    /**
     * Execute an API skill via Fetch
     */
    private async executeApiSkill(skill: SkillDefinition, params: any, overrides?: any): Promise<any> {
        const config = { ...skill.config, ...overrides };
        let url = config.url;
        const queryParams = new URLSearchParams();

        for (const [key, value] of Object.entries(params)) {
            if (url.includes(`{${key}}`)) {
                url = url.replace(`{${key}}`, String(value));
            } else if (config.method === 'GET') {
                queryParams.append(key, String(value));
            }
        }

        if (config.method === 'GET' && queryParams.toString()) {
            url += `?${queryParams.toString()}`;
        }

        const headers = {
            'Content-Type': 'application/json',
            ...(config.headers || {})
        };

        if (config.authType === 'bearer' && config.apiKey) {
            headers['Authorization'] = `Bearer ${config.apiKey}`;
        }

        const response = await fetch(url, {
            method: config.method || 'GET',
            headers,
            body: config.method !== 'GET' ? JSON.stringify(params) : undefined
        });

        if (!response.ok) {
            throw new Error(`API call failed: ${response.status} ${response.statusText}`);
        }

        const text = await response.text();
        try {
            return JSON.parse(text);
        } catch {
            return { text };
        }
    }

    /**
     * Execute a Node.js script skill via VM
     */
    private async executeScriptSkill(skill: SkillDefinition, params: any, overrides?: any): Promise<any> {
        const scriptContent = skill.config.script;
        if (!scriptContent) throw new Error('No script content found in skill config');

        const sandbox = {
            params,
            console: {
                log: (...args: any[]) => console.log('[Script Log]', ...args),
                error: (...args: any[]) => console.error('[Script Error]', ...args),
                warn: (...args: any[]) => console.warn('[Script Warn]', ...args)
            },
            result: null as any
        };

        const vm = require('vm');
        const context = vm.createContext(sandbox);

        const wrappedScript = `
            (async () => {
                try {
                    ${scriptContent}
                } catch (e) {
                    throw e;
                }
            })()
        `;

        try {
            const scriptResult = await vm.runInContext(wrappedScript, context, { timeout: 5000 });
            return scriptResult !== undefined ? scriptResult : sandbox.result;
        } catch (error: any) {
            throw new Error(`Script execution failed: ${error.message}`);
        }
    }

    /**
     * Execute a Docker container skill (Local Environment)
     */
    private async executeDockerSkill(skill: SkillDefinition, params: any, overrides?: any): Promise<any> {
        // Only works in environments with Docker Access (Local/Tauri/Custom)
        try {
            const Docker = require('dockerode');
            const docker = new Docker();

            const image = skill.config.image;
            if (!image) throw new Error('No Docker image specified');

            const env = [`SKILL_PARAMS=${JSON.stringify(params)}`];
            for (const [key, value] of Object.entries(params)) {
                if (typeof value === 'string' || typeof value === 'number') {
                    env.push(`${key.toUpperCase()}=${value}`);
                }
            }

            const stream = require('stream');
            const outputStream = new stream.PassThrough();
            let outputData = '';
            outputStream.on('data', (chunk: Buffer) => outputData += chunk.toString());

            const cmd = skill.config.command ? parseArgsStringToArgv(skill.config.command) : [];

            const [data] = await docker.run(image, cmd, outputStream, {
                Env: env,
                HostConfig: { AutoRemove: true }
            });

            if (data.StatusCode !== 0) {
                throw new Error(`Docker exited with ${data.StatusCode}: ${outputData}`);
            }

            try {
                return JSON.parse(outputData.trim());
            } catch {
                return { output: outputData.trim() };
            }
        } catch (err: any) {
            if (err.code === 'ENOENT' || err.message.includes('socket')) {
                throw new Error(`Docker not available in this environment. Try using "container" type.`);
            }
            throw err;
        }
    }

}
// Note: executeContainerSkill removed (was SaaS-specific Fly.io cloud execution)
// executeDockerSkill remains for local/self-hosted Docker execution
